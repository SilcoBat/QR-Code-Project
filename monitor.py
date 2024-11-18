from datetime import datetime
import paramiko
import json
import time
from mysql.connector import errors
import mysql.connector
import sqlite3
import pandas as pd
from datetime import datetime
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import time
# MariaDB kapcsolat beállítása
def get_db_connection(retries=3, delay=5):
    for attempt in range(retries):
        try:
            return mysql.connector.connect(
                host='10.10.2.15',
                database='paperless',
                user='root',
                password='admin321'
            )
        except (errors.InterfaceError, errors.OperationalError, errors.DatabaseError, TimeoutError, errors.ProgrammingError) as e:
            print(f"Hiba történt a kapcsolódás során: {e}")
            if attempt < retries - 1:
                print(f"Újrapróbálkozás {delay} másodperc múlva...")
                time.sleep(delay)
            else:
                raise

# Eszközök lekérdezése az adatbázisból
def fetch_devices_from_db():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT device_id, device_name FROM raspberrydevices")
        devices = cursor.fetchall()
    except (errors.InterfaceError, errors.OperationalError, errors.DatabaseError, TimeoutError, errors.ProgrammingError) as e:
        print(f"Hiba történt az eszközök lekérdezése során: {e}")
        devices = []
    finally:
        cursor.close()
        conn.close()
    return devices

# SSH parancs végrehajtása a Raspberry Pi-n
def execute_command_on_pi(ip, username, password, command, retries=3, delay=5):
    for attempt in range(retries):
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, username=username, password=password, timeout=10)  # 10 másodperces timeout

            stdin, stdout, stderr = client.exec_command(command)
            output = stdout.read().decode().strip()  # A parancs normál kimenete
            error_output = stderr.read().decode().strip()  # A parancs hibakimenete

            client.close()

            if error_output:
                # Ha hiba történt, visszatérünk a hibaüzenettel
                return f"Error: {error_output}"

            return output

        except (paramiko.ssh_exception.NoValidConnectionsError, paramiko.ssh_exception.SSHException, Exception) as e:
            print(f"SSH hiba történt: {e}")
            if attempt < retries - 1:
                print(f"Újrapróbálkozás {delay} másodperc múlva...")
                time.sleep(delay)
            else:
                return f"Device is offline or SSH error after {retries} attempts: {str(e)}"

# Virtual environment és csomagok ellenőrzése
def check_virtualenv_and_packages(ip, username, password):
    commands = """
    # Install git if not present
    if ! command -v git &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y git
    fi

    # Create virtual environment if it doesn't exist
    if [ ! -d "/home/user/myenv" ]; then
        python3 -m venv /home/user/myenv
        source /home/user/myenv/bin/activate
        pip install ttkbootstrap mysql-connector Pillow
        pip install netifaces
    else
        source /home/user/myenv/bin/activate
    fi

    # Clone or update the repository
    cd /home/user
    if [ ! -d "QR-Code-Project" ]; then
        git clone https://github.com/SilcoBat/QR-Code-Project.git || echo "Git clone failed"
    else
        cd QR-Code-Project && git pull || echo "Git pull failed"
    fi

    # Verify the directory and copy files if they exist
    if [ -d "/home/user/QR-Code-Project" ]; then
        cp /home/user/QR-Code-Project/V3.7.py /home/user/Desktop/ || echo "V3.7.py copy failed"
        cp /home/user/QR-Code-Project/logo.png /home/user/ || echo "logo.png copy failed"
        echo "Installed"
    else
        echo "QR-Code-Project directory not found"
    fi
    """
    return execute_command_on_pi(ip, username, password, commands)



# CPU, RAM, I/O statisztikák és SD kártya egészségi állapotának lekérése
# CPU, RAM, I/O statisztikák és SD kártya egészségi állapotának lekérése
def gather_device_stats(ip, username, password):
    stats = {}

    # Hostname lekérdezése
    hostname_command = "hostname"
    hostname_output = execute_command_on_pi(ip, username, password, hostname_command)
    stats["hostname"] = hostname_output if hostname_output else "N/A"
    
    # Hőmérséklet lekérdezése
    temp_command = "cat /sys/class/thermal/thermal_zone0/temp"
    temp_output = execute_command_on_pi(ip, username, password, temp_command)
    if temp_output.isdigit():
        stats["temperature"] = int(temp_output) / 1000
    else:
        stats["temperature"] = "N/A"

    # CPU használat lekérdezése alternatív parancs
    cpu_command = "top -bn1 | grep 'Cpu(s)' | awk '{print 100 - $8}'"
    cpu_output = execute_command_on_pi(ip, username, password, cpu_command)
    try:
        stats["cpu_usage"] = float(cpu_output)
    except ValueError:
        stats["cpu_usage"] = "N/A"

    # RAM használat lekérdezése
    ram_command = "free -m | awk 'NR==2{printf \"%s/%sMB (%.2f%%)\", $3,$2,$3*100/$2 }'"
    ram_output = execute_command_on_pi(ip, username, password, ram_command)
    stats["ram_usage"] = ram_output if ram_output else "N/A"

    # I/O statisztikák lekérdezése alternatív parancs
    io_command = "cat /proc/diskstats | grep mmcblk0"
    io_output = execute_command_on_pi(ip, username, password, io_command)
    if "mmcblk0" in io_output:
        io_lines = io_output.splitlines()
        for line in io_lines:
            io_data = line.split()
            read_sectors = io_data[5]  # Olvasott szektorok száma
            write_sectors = io_data[9]  # Írt szektorok száma
            stats["io_stats"] = f"Read sectors: {read_sectors}, Write sectors: {write_sectors}"
    else:
        stats["io_stats"] = "N/A"

    # SD kártya egészségi állapotának ellenőrzése
    sd_health_command = "dmesg | grep mmcblk0 | wc -l"
    sd_health_output = execute_command_on_pi(ip, username, password, sd_health_command)
    try:
        error_count = int(sd_health_output)
        if error_count > 10:
            stats["sd_health"] = f"Warning: {error_count} errors detected"
        else:
            stats["sd_health"] = "Healthy or no significant errors"
    except ValueError:
        stats["sd_health"] = "N/A"

    return stats



# Program leállítása
def stop_program(ip, username, password):
    command = "pkill -f V3.7.py"
    execute_command_on_pi(ip, username, password, command)
    print(f"Program stopped on {ip}.")

# Program indítása
def start_program(ip, username, password):
    command = "/bin/bash -c 'source /home/user/myenv/bin/activate && nohup python /home/user/Desktop/V3.7.py > /home/user/program_output.log 2>&1 &'"
    execute_command_on_pi(ip, username, password, command)
    print(f"Program started on {ip}.")

# Program státuszának ellenőrzése
def check_program_status(ip, username, password):
    command = "pgrep -f V3.7.py"
    result = execute_command_on_pi(ip, username, password, command)
    return "Running" if result else "Disabled"

# Ellenőrzési időablakok kezelése
def check_time_window():
    current_time = datetime.now().time()
    
    # Stop the program between 22:00 - 22:05
    stop_start_time = datetime.strptime("22:00", "%H:%M").time()
    stop_end_time = datetime.strptime("22:05", "%H:%M").time()

    # Start the program between 05:50 - 06:00
    start_start_time = datetime.strptime("05:50", "%H:%M").time()
    start_end_time = datetime.strptime("06:00", "%H:%M").time()

    return current_time, stop_start_time, stop_end_time, start_start_time, start_end_time


# Eszköznév lekérdezése SSH-n keresztül
def get_device_name(ip, username, password):
    command = "hostname"  # Ezzel a parancsal lekérdezzük az eszköz nevét
    return execute_command_on_pi(ip, username, password, command)


# Monitorozási funkció Raspberry Pi-khez (adatbázisból töltjük be az eszközöket)
def monitor_devices():
    current_time, stop_start_time, stop_end_time, start_start_time, start_end_time = check_time_window()

    devices = fetch_devices_from_db()  # Eszközök lekérdezése az adatbázisból
    updated_devices = []  # Frissített eszközadatok tárolására

    for device in devices:
        ip = device["device_id"]
        hostname = device["device_name"]
        username = "user"
        password = "user"

        print(f"Monitoring device: {ip}")

        # Ellenőrizzük, hogy az eszköz online-e
        uptime_command = "uptime -p"
        uptime = execute_command_on_pi(ip, username, password, uptime_command)

        if "Device is offline" in uptime or uptime == "":
            # Ha az eszköz nem érhető el, az adatbázisból vesszük a nevet és az IP címet
            device_data = {
                "status": "Offline",
                "uptime": "--",
                "temperature": "--",
                "cpu_usage": "--",
                "ram_usage": "--",
                "io_stats": "--",
                "sd_health": "--",
                "program_status": "--",
                "file_exists": "--",
                "name": hostname,  # Az adatbázisból származó hostname
                "ip": ip           # Az adatbázisból származó IP cím
            }
        else:
            device_data = {
                "status": "Online",
                "uptime": uptime,
                "name": hostname,
                "ip": ip
            }

            # Hőmérséklet lekérdezése
            temp_command = "cat /sys/class/thermal/thermal_zone0/temp"
            temp = execute_command_on_pi(ip, username, password, temp_command)
            if temp.isdigit():
                temp_celsius = int(temp) / 1000
                device_data["temperature"] = temp_celsius
            else:
                device_data["temperature"] = "--"

            # I/O statisztikák (SD kártya I/O)
            io_command = "iostat -d mmcblk0"
            io_stats = execute_command_on_pi(ip, username, password, io_command)
            if "mmcblk0" in io_stats:
                io_lines = io_stats.splitlines()
                for line in io_lines:
                    if 'mmcblk0' in line:
                        io_data = line.split()
                        read_speed = io_data[1]  # kB_read/s
                        write_speed = io_data[2]  # kB_wrtn/s
                        device_data["io_stats"] = f"Read: {read_speed} kB/s, Write: {write_speed} kB/s"
            else:
                device_data["io_stats"] = "--"

            # CPU használat
            cpu_command = "mpstat | grep all | awk '{print 100 - $NF}'"
            cpu_usage = execute_command_on_pi(ip, username, password, cpu_command)
            try:
                device_data["cpu_usage"] = float(cpu_usage)
            except ValueError:
                device_data["cpu_usage"] = "--"

            # RAM használat
            ram_command = "free -m | awk 'NR==2{printf \"%s/%sMB (%.2f%%)\", $3,$2,$3*100/$2 }'"
            ram_usage = execute_command_on_pi(ip, username, password, ram_command)
            device_data["ram_usage"] = ram_usage if ram_usage else "--"

            # SD kártya állapot
            sd_health_command = "dmesg | grep mmcblk0"
            sd_health = execute_command_on_pi(ip, username, password, sd_health_command)
            if "error" in sd_health.lower():
                device_data["sd_health"] = "Error detected"
            else:
                device_data["sd_health"] = "Healthy or no errors"

            # Program állapota és csomagok ellenőrzése
            program_status = check_program_status(ip, username, password)
            device_data["program_status"] = program_status
            device_data["file_exists"] = check_virtualenv_and_packages(ip, username, password)

        # Az adott eszköz adatainak hozzáadása a frissített eszközök listájához
        updated_devices.append({
            "device_id": ip,
            "device_name": hostname,
            **device_data
        })

        # Kimenet az eszköz állapotáról
        print(f"Uptime: {device_data['uptime']}")
        print(f"Device Name: {device_data['name']}")
        print(f"Hőmérséklet: {device_data['temperature']} °C")
        print(f"CPU Usage: {device_data['cpu_usage']}%")
        print(f"RAM Usage: {device_data['ram_usage']}")
        print(f"I/O statisztikák:\n{device_data['io_stats']}")
        print(f"SD kártya állapot: {device_data['sd_health']}")
        print(f"Program Status: {device_data['program_status']}")
        print(f"File Exists: {device_data['file_exists']}")
        print("-" * 40)

    # Frissített adatok mentése JSON fájlba
    with open('data/devices.json', 'w') as f:
        json.dump(updated_devices, f, indent=4)


class DatabaseHandler:
    def __init__(self, database_path, retries=3, delay=5):
        self.database_path = database_path
        self.db_url = f'file:{self.database_path}?mode=rw&uri=true'
        self.conn = None
        self.cursor = None

        for attempt in range(retries):
            try:
                self.conn = sqlite3.connect(self.db_url, uri=True)
                self.cursor = self.conn.cursor()
                break  # Exit the loop if connection is successful
            except sqlite3.Error as e:
                print(f"Hiba történt az adatbázis kapcsolódás során: {e}")
                if attempt < retries - 1:
                    print(f"Újrapróbálkozás {delay} másodperc múlva...")
                    time.sleep(delay)
                else:
                    print("Nem sikerült kapcsolódni az adatbázishoz a megadott próbálkozások után.")

    def __del__(self):
        # Destruktor: bezárjuk a kapcsolatot, ha az még nyitva van
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def import_data_from_excel(self, excel_file_path, table_name):
        connection = None
        cursor = None
        try:
            # Az aktuális dátum lekérése és formázása
            datum = datetime.now().strftime("%Y%m%d")

            # Az új adatbázis fájl neve az aktuális dátummal
            uj_db_fajl_nev = f"Z:\\SHARED FOLDERS\\Sqlite_db\\backup\\testdbtest_db_{datum}.db"

            # Mappa tartalmának törlése
            self.clear_directory(r"Z:\SHARED FOLDERS\Sqlite_db\backup")

            # Excel fájl beolvasása
            df_excel = pd.read_excel(excel_file_path)

            # SQLite adatbázis kapcsolat létrehozása
            connection = sqlite3.connect(uj_db_fajl_nev)
            cursor = connection.cursor()

            # DataFrame beszúrása az SQLite adatbázisba, csak ha a tábla még nem létezik
            df_excel.to_sql(table_name, connection, if_exists='replace', index=False)

            print("Adatok sikeresen migrálva az Excel fájlból az SQLite adatbázisba.")

            # Az új adatbázis fájl neve visszatérítése
            return uj_db_fajl_nev
        except FileNotFoundError as fnf_error:
            print(f"A fájl nem található: {fnf_error}")
        except pd.errors.EmptyDataError:
            print("Az Excel fájl üres.")
        except sqlite3.Error as db_error:
            print(f"Hiba történt az SQLite adatbázis művelet során: {db_error}")
        except Exception as e:
            print(f"Hiba történt: {e}")
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def clear_directory(self, directory_path):
        for file_name in os.listdir(directory_path):
            file_path = os.path.join(directory_path, file_name)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    os.rmdir(file_path)
            except FileNotFoundError as fnf_error:
                print(f"A fájl nem található: {fnf_error}")
            except PermissionError as perm_error:
                print(f"Nincs megfelelő jogosultság a fájl törléséhez: {perm_error}")
            except Exception as e:
                print(f"Hiba történt a fájl törlésekor: {e}")

    def alter_table_column_name(self, table_name, old_column_name, new_column_name):
        try:
            self.cursor.execute(f"PRAGMA foreign_keys=off;")
            self.cursor.execute(f"ALTER TABLE {table_name} RENAME COLUMN '{old_column_name}' TO '{new_column_name}';")
            self.cursor.execute(f"PRAGMA foreign_keys=on;")
            print(f"Oszlop átnevezése sikeres: '{old_column_name}' -> '{new_column_name}'")
        except Exception as e:
            print(f"Hiba történt az oszlop átnevezése során: {e}")
            
          

class WatchdogHandler(FileSystemEventHandler):
    def __init__(self, db_handler, excel_file_path, table_name):
        self.db_handler = db_handler
        self.excel_file_path = excel_file_path
        self.table_name = table_name

    def on_modified(self, event):
        if event.src_path == self.excel_file_path:
            print(f"Módosítás észlelve: {event.src_path}")
            self.db_handler.import_data_from_excel(self.excel_file_path, self.table_name)

# Példa az osztály használatára
database_path = r'Z:\SHARED FOLDERS\Sqlite_db\testdb\test_db.db'
excel_file_path = "//10.10.2.187/ftp.reports/generated/Administrator_AUTO.ITEM.MASTER.DUMP.xlsx"
table_name = "t_dump"

db_handler = DatabaseHandler(database_path)
new_db_name = db_handler.import_data_from_excel(excel_file_path, table_name)

def start_watchdog():
    # Watchdog inicializálása
    watchdog_handler = WatchdogHandler(db_handler, excel_file_path, table_name)
    observer = Observer()
    observer.schedule(watchdog_handler, path=os.path.dirname(excel_file_path), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
def delete_duplicates():
    # Adatbázis csatlakozás
    connection = mysql.connector.connect(
                host='10.10.2.15',
                database='paperless',
                user='root',
                password='admin321'
            )
    
    cursor = connection.cursor()

    # Rekordok számának lekérdezése
    count_records = """
        SELECT COUNT(*) FROM workorders;
    """
    cursor.execute(count_records)
    record_count = cursor.fetchone()[0]
    print(f"A 'workorders' táblában jelenleg {record_count} rekord van.")

    # Előző rekordok számának betöltése a fájlból
    with open('data/database_change.json', 'r') as file:
        previous_data = json.load(file)
        previous_record_count = previous_data.get("record_count", 0)

    # Csak akkor futtatjuk a törlési folyamatot, ha a rekordok száma nőtt
    if record_count > previous_record_count:
        # Ellenőrizzük, hogy a mentés tábla már létezik-e
        check_table_exists = """
            SHOW TABLES LIKE 'workorderstest_backup';
        """
        cursor.execute(check_table_exists)
        backup_exists = cursor.fetchone()

        if backup_exists:
            # Ha létezik a backup tábla, először töröljük annak tartalmát
            delete_backup_content = """
                DELETE FROM workorderstest_backup;
            """
            cursor.execute(delete_backup_content)
            print("A 'workorderstest_backup' tábla tartalma törölve lett.")

        else:
            # Ha nem létezik, akkor létrehozzuk a backup táblát
            create_backup_table = """
                CREATE TABLE workorderstest_backup LIKE workorders;
            """
            cursor.execute(create_backup_table)
            print("Létrehoztuk a 'workorderstest_backup' táblát.")

        # Aktuális adatok másolása a backup táblába
        insert_into_backup = """
            INSERT INTO workorderstest_backup
            SELECT * FROM workorders;
        """
        cursor.execute(insert_into_backup)
        print("Az aktuális adatok elmentésre kerültek a 'workorderstest_backup' táblába.")

        # SQL lekérdezés a duplikált rekordok megtalálásához a WO és PN alapján
        find_duplicates = """
            SELECT WO, PN, GROUP_CONCAT(id ORDER BY HIERARCHY DESC, id ASC) AS ids
            FROM workorders
            GROUP BY WO, PN
            HAVING COUNT(*) > 1;
        """
        
        cursor.execute(find_duplicates)
        duplicates = cursor.fetchall()

        # Törlés végrehajtása minden duplikált rekord esetén, kivéve azt, amelyiknek a HIERARCHY oszlopa nem üres
        for row in duplicates:
            wo, pn, ids = row
            id_list = ids.split(',')
            id_to_keep = id_list[0]  # Az első rekord az, amelyiknek a HIERARCHY oszlopa nem üres, vagy a legkisebb ID-val rendelkezik

            print(f"Törlés folyamatban: WO {wo}, PN {pn}, megtartva ID {id_to_keep}")

            # Törlés minden rekord esetén, kivéve a megtartandó ID-t
            delete_query = """
                DELETE FROM workorders
                WHERE WO = %s AND PN = %s AND id != %s;
            """
            cursor.execute(delete_query, (wo, pn, id_to_keep))
        
        # Változtatások véglegesítése
        connection.commit()
        print("A duplikált rekordok törölve lettek.")

        # Rekordok számának frissítése a fájlban
        with open('data/database_change.json', 'w') as file:
            json.dump({"record_count": record_count}, file)
    else:
        print("Nincs változás a rekordok számában, a törlési folyamat nem futott le.")

    # Kapcsolat lezárása
    cursor.close()
    connection.close()

if __name__ == "__main__":
    # Watchdog indítása külön threadben
    watchdog_thread = threading.Thread(target=start_watchdog, daemon=True)
    watchdog_thread.start()

    # A fő program tovább futhat, miközben a watchdog figyel egy másik threadben
    print("Watchdog elindult külön threadben.")
    # Végtelen ciklus a rendszeres futtatáshoz
    while True:
        delete_duplicates()
        monitor_devices()
        print("Waiting for the next cycle...")
        time.sleep(10)  # 10 másodpercenként újra futtatja a monitorozást
