import paramiko
import os
import time
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import threading

class RaspberryScheduler:
    def __init__(self, db_config, virtual_env_path, script_path):
        self.db_config = db_config
        self.virtual_env_path = virtual_env_path
        self.script_path = script_path
        self.last_stop_time = None
        self.last_start_time = None
        self.ssh_username = "user"
        self.ssh_password = "user"
        self.ips = []  # Cache-elt IP címek

    def connect_to_database(self):
        """Adatbáziskapcsolat létrehozása."""
        try:
            return mysql.connector.connect(**self.db_config)
        except Error as e:
            print(f"Adatbázis hiba: {e}")
            return None

    def fetch_ips(self, connection):
        """IP címek frissítése az adatbázisból."""
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT device_id FROM raspberrydevices")
            return [row[0] for row in cursor.fetchall() if row[0].startswith("10.10.40.")]
        except Error as e:
            print(f"Lekérdezési hiba: {e}")
            return []

    def execute_remote_command(self, ip, command):
        """Parancs végrehajtása SSH-n keresztül időkorláttal."""
        try:
            with paramiko.SSHClient() as client:
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(ip, username=self.ssh_username, password=self.ssh_password, timeout=10)
                stdin, stdout, stderr = client.exec_command(command, timeout=15)
                exit_status = stdout.channel.recv_exit_status()
                
                if exit_status != 0:
                    error = stderr.read().decode().strip()
                    print(f"Hiba {ip}-n ({exit_status}): {error}")
                else:
                    print(f"Sikeres végrehajtás {ip}-n")
        except Exception as e:
            print(f"SSH hiba {ip}-n: {str(e)}")

    def stop_program(self, ip):
        """Program leállítása egy eszközön."""
        self.execute_remote_command(ip, f"pkill -f {self.script_path}")

    def start_program(self, ip):
        """Program indítása egy eszközön."""
        cmd = f"source {self.virtual_env_path}/bin/activate && nohup python3 {self.script_path} >/dev/null 2>&1 &"
        self.execute_remote_command(ip, cmd)

    def update_ips(self):
        """IP címek frissítése szálban."""
        connection = self.connect_to_database()
        if connection:
            self.ips = self.fetch_ips(connection)
            connection.close()

    def schedule_tasks(self):
        """Fő ütemező ciklus."""
        while True:
            try:
                now = datetime.now()
                
                # IP címek frissítése minden percben
                if now.second == 0:
                    threading.Thread(target=self.update_ips).start()

                # Program leállítás 23:15-kor
                if now.hour == 23 and now.minute == 15:
                    if not self.last_stop_time or self.last_stop_time.date() != now.date():
                        for ip in self.ips:
                            threading.Thread(target=self.stop_program, args=(ip,)).start()
                        self.last_stop_time = now

                # Program indítás 6:55-kor
                if now.hour == 6 and now.minute == 55:
                    if not self.last_start_time or self.last_start_time.date() != now.date():
                        for ip in self.ips:
                            threading.Thread(target=self.start_program, args=(ip,)).start()
                        self.last_start_time = now

                time.sleep(1)

            except Exception as e:
                print(f"Kritikus hiba: {str(e)}")
                time.sleep(60)

if __name__ == "__main__":
    db_config = {
        'host': '10.10.2.15',
        'user': 'root',
        'password': 'admin321',
        'database': 'paperless'
    }
    
    scheduler = RaspberryScheduler(
        db_config=db_config,
        virtual_env_path="/home/user/myenv",
        script_path="/home/user/Desktop/V3.7.py"
    )
    
    scheduler.schedule_tasks()
