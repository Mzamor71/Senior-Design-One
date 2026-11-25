
import csv
import subprocess
import tempfile
import time
import threading
import os
from datetime import datetime
from pathlib import Path

BROKER = "localhost"
TOPIC = "performance/test"
MESSAGE_COUNTS = [100, 1000, 10000]

MQTT_USERNAME = "perfuser"
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")

if not MQTT_PASSWORD:
	raise SystemExit(
		"Please set the MQTT_PASSWORD environment variable before running."
	)

OUTPUT_FILE = Path("mqtt_performance_results.csv")


def get_broker_resources():
	"""Return approximate Mosquitto CPU and memory measurements."""
	result = subprocess.run(
		["ps", "-C", "mosquitto", "-o", "%cpu=,%mem=,rss="],
	capture_output = True,
	text = True,
	check = False,
	)
	
	measurements = []
	
	for line in result.stdout.splitlines():
		parts = line.split()
		if len(parts) == 3:
			try:
				cpu, memory.rss = map(float, parts)
				measurements.append((cpu, memory, rss))
			except ValueError:
					pass
	if not measurements:
		return None

	return(
		max(item[0] for item in measurements),
		max(item[1] for item in measurements),
		max(item[2] for item in measurements),
	)

def run_test(message_count):
	print(f"\nTesting {message_count:,} messages...")

	#Store subscriber output in a temporary file
	with tempfile.TemporaryFile(mode="w+t") as received_file:
		subscriber = subprocess.Popen(
			[
				"mosquitto_sub",
				"-h", BROKER,
				"-u", MQTT_USERNAME,
				"-P", MQTT_PASSWORD,
				"-t", TOPIC,
				"-C", str(message_count),
				"-W", "30",
			],
			stdout=received_file,
			stderr=subprocess.PIPE,
			text=True,
		)

		#Allow the subscriber to connect before publishing.
		time.sleep(0.5)
		
		if subscriber.poll() is not None:
			error = subscriber.stderr.read()
			print("ERROR: Subscriber failed to start.")
			print(error)
			return None
		stop_monitor = threading.Event()
		resource_samples = []

		def monitor_resources():
			while not stop_monitor.is_set():
				sample = get_broker_resources()
				if sample:
					resource_samples.append(sample)
				stop_monitor.wait(0.2)

		monitor = threading.Thread(
			target=monitor_resources,
			daemon=True,
		)
		monitor.start()

		messages = "".join(
			f"message-{i}\n" for i in range(1, message_count + 1)
		)

		start = time.perf_counter()

		try:
			publisher = subprocess.run(
				[
					"mosquitto_pub",
					"-h", BROKER,
					"-u", MQTT_USERNAME,
					"-P", MQTT_PASSWORD,
					"-t", TOPIC,
					"-l",
				],
				input=messages,
				capture_output=True,
				text=True,
				timeout=60,
				check=False,
			)

			if publisher.returncode != 0:
				raise RuntimeError(
					publisher.stderr.strip() or "Publisher failed."
				)

			subscriber.wait(timeout=35)

		except (subprocess.TimeoutExpired, RuntimeError) as error:
			print(f"ERROR: {error}")
			subsciber.terminate()
			try:
				subscriber.wait(timeout=3)
			except subprocess.TimeoutExpired:
				subscriber.kill()
				subscriber.wait()
			return None

		finally:
			stop_monitor.set()
			monitor.join(timeout=2)
		elapsed = time.perf_counter() - start
		
		received_file.seek(0)
		received = sum(1 for line in  received_file if line.strip())

		throughput = received / elapsed if elapsed > 0 else 0
		delivery = (received / message_count) * 100

		if resource_samples:
			max_cpu = max(sample[0] for sample in resource_samples)
			max_mem = max(sample[1] for sample in resource_samples)
			max_rss = max(sample[2] for sample in resource_samples)
		else:
			max_cpu = max_mem = max_rss = None
		
		result = {
			"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
			"messages_published": message_count,
			"messages_received": received,
			"elapsed_seconds": round(elapsed, 4),
			"throughput_msg_per_sec": round(throughput, 2),
			"delivery_percent": round(delivery, 2),
			"max_sampled_cpu_percent": max_cpu,
			"max_sampled_memory_percent": max_mem,
			"max_sampled_rss_kib": max_rss,
			"qos": 0,
		}

		print(f"Published: {message_count:,}")
		print(f"Received: {received:,}")
		print(f"Elapesed: {elapsed:.4f} seconds")
		print(f"Throughput: {throughput:.2f} messages/second")
		print(f"Delivery: {delivery:.2f}%")

		if max_cpu is not None:
			print(f"Sampled CPU: {max_cpu:.1f}%")
			print(f"Sampled RAM: {max_rss / 1024:.2f} MiB RSS")
		else:
			print("Resource measurements unavailable")

		if received == message_count:
			print("Result: PASS")
		else:
			print("Result: CHECK - message counts differ")
		return result

def main():
	if not OUTPUT_FILE.exists():
		with OUTPUT_FILE.open("w", newline="") as file:
			writer = csv.DictWriter(
				file,
				fieldnames=[
					"timestamp",
					"messages_published",
					"messages_received",
					"elapsed_seconds",
					"throughput_msg_per_sec",
					"delivery_percent",
					"max_sampled_cpu_percent",
					"max_sampled_memory_percent",
					"max_sampled_rss_kib",
					"qos",
				],
			)
			writer.writeheader()

	print("Mosquitto MQTT Performance Evaluation")
	print(f"Broker: {BROKER}")
	print(f"Topic: {TOPIC}")
	print(f"Results will be saved to: {OUTPUT_FILE.resolve()}")

	for count in MESSAGE_COUNTS:
		result = run_test(count)

		if result is not None:
			with OUTPUT_FILE.open("a", newline="") as file:
				writer = csv.DictWriter(file,fieldnames=result.keys())
				writer.writerow(result)

	print("\nAll tests completed.")
	print(f"Results saved to {OUTPUT_FILE.resolve()}")

if __name__ == "__main__":
	print("Starting MQTT performance test...", flush=True)
	main()
