import os
if os.environ.get('DISPLAY','') == '':
    print('no display found. Using :0.0')
    os.environ.__setitem__('DISPLAY', ':0.0')
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from ttkbootstrap import Style

import mysql.connector
from mysql.connector import Error, errors  # Added 'errors' for error handling in execute_query
import time
from datetime import datetime
from PIL import Image, ImageTk
import re
import platform
import socket
import netifaces as ni
import threading



class RaspberryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.device_name = socket.gethostname()
        self.raspberry_id = socket.gethostbyname(self.device_name)
        self.workstation_id = "2"
        self.style = Style('cyborg')
        self.title("Raspberry App")
        
        # Initialize connection
        self.db_connection = None
        self.connection_window = None
        self.stop_thread = False
        self.angle = 0
        self.is_reconnecting = False  # Új változó az állapot követéséhez

        self.conn = self.connect_to_database()
        if self.conn:
            self.cursor = self.conn.cursor()
        else:
            self.cursor = None  # Biztonsági intézkedés sikertelen kapcsolat esetén
            print("Failed to initialize the database connection.")

        self.login_page_frame = LoginPage(self)
        self.main_page_frame = MainPage(self)

        self.show_login_page()
        self.login_page_frame.set_focus()

        # Adjust the network interface based on the operating system
        wifi_interface = 'wlan0' if platform.system() != 'Windows' else 'Wi-Fi'

        try:
            if platform.system() == 'Windows':
                # Fetch IP address for Windows
                ip_address = socket.gethostbyname(socket.gethostname())
            else:
                # Fetch IP address for Linux (e.g., Raspberry Pi)
                ip_address = ni.ifaddresses(wifi_interface)[ni.AF_INET][0]['addr']
        except KeyError:
            ip_address = 'No WiFi connection or interface not available'
        except Exception as e:
            ip_address = f"Error fetching IP: {e}"

        self.raspberry_id = ip_address
        print("Device name: ", self.device_name)
        print("Raspberry id: ", self.raspberry_id)
        print(f"WiFi IP address: {ip_address}")

    def connect_to_database(self):
        """Próbál csatlakozni az adatbázishoz."""
        try:
            print("Attempting to connect to the database...")
            connection = mysql.connector.connect(
                host="10.10.2.15",
                user="root",
                password="admin321",
                database="paperless",
                connection_timeout=5
            )
            if connection.is_connected():
                print("Sikeres csatlakozás az adatbázishoz!")
                self.db_connection = connection
                if self.connection_window:
                    self.connection_window.destroy()
                    self.connection_window = None
                self.is_reconnecting = False  # Újracsatlakozási folyamat lezárása
                return connection
        except mysql.connector.Error as e:
            # Kezeljük a specifikus hibakódokat
            if e.errno == 2003:  # Can't connect to MySQL server
                print(f"MySQL server nem érhető el: {e}")
                self.show_connection_window()  # Megjelenítjük az újracsatlakozási ablakot
                self.conn = None
            elif e.errno == 1045:  # Access denied for user
                print("Helytelen felhasználónév vagy jelszó!")
            elif e.errno == 1049:  # Unknown database
                print("Az adatbázis nem létezik!")
            else:
                print(f"Ismeretlen adatbázis hiba: {e}")
            return None


    def ensure_connection(self):
        """Biztosítja az adatbázis kapcsolatot."""
        if self.db_connection is None or not self.db_connection.is_connected():
            if not self.is_reconnecting:
                print("Nincs kapcsolat az adatbázissal. Újracsatlakozás...")
                self.is_reconnecting = True
                self.show_connection_window()
                threading.Thread(target=self.attempt_reconnection, daemon=True).start()
            return False
        self.conn = self.db_connection  # Frissítsd a self.conn-t az aktuális kapcsolattal
        return True



    def attempt_reconnection(self):
        """Folyamatosan próbál csatlakozni az adatbázishoz."""
        while self.is_reconnecting:
            connection = self.connect_to_database()
            if connection and connection.is_connected():
                print("Sikeres csatlakozás az adatbázishoz!")
                self.db_connection = connection
                self.is_reconnecting = False
                self.after(0, self.hide_connection_window)  # Ablak elrejtése a főszálban
                return
            else:
                print("[DEBUG] Újracsatlakozás sikertelen. Próbálkozik...")
            time.sleep(5)  # Várakozás a következő próbálkozás előtt
        print("[DEBUG] Újracsatlakozás nem sikerült. Manuális beavatkozás szükséges.")


    def show_connection_window(self):
        """Felugró ablak megjelenítése az újracsatlakozás alatt."""
        if self.connection_window is None or not self.connection_window.winfo_exists():
            self.connection_window = tk.Toplevel(self)
            self.connection_window.title("Kapcsolódási probléma")
            self.connection_window.geometry("300x150")
            tk.Label(
                self.connection_window,
                text="Kapcsolat az adatbázishoz megszakadt.\nPróbál újracsatlakozni...",
                pady=10
            ).pack()

            # Hozzáadunk egy spinning wheel animációt
            self.canvas = tk.Canvas(self.connection_window, width=100, height=100, bg="white", highlightthickness=0)
            self.canvas.pack(pady=10)
            self.arc = self.canvas.create_arc(10, 10, 90, 90, start=0, extent=30, fill="blue")
            self.animate_spinner()

            self.connection_window.protocol("WM_DELETE_WINDOW", lambda: None)  # Letiltjuk a bezárást

    def animate_spinner(self):
        """Forgó kerék animáció."""
        if self.connection_window and self.connection_window.winfo_exists() and hasattr(self, 'canvas'):
            self.angle += 10  # Forgatási szög növelése
            self.canvas.itemconfig(self.arc, start=self.angle)  # Szög frissítése
            self.connection_window.after(50, self.animate_spinner)  # Animáció folytatása
        else:
            print("[DEBUG] Spinner animation stopped: Connection window or canvas no longer exists.")

    def hide_connection_window(self):
        """Kapcsolódási ablak elrejtése."""
        if self.connection_window and self.connection_window.winfo_exists():
            self.connection_window.destroy()
            self.connection_window = None
            print("[DEBUG] Connection window hidden.")

    def execute_query(self, query, params=None, fetchone=False, caller=None):
        try:
            # Check if connection is active, if not, reconnect
            if self.conn is None or not self.conn.is_connected():
                print("Database connection lost. Reconnecting...")
                self.connect_to_database()
    
            if self.conn is not None and self.conn.is_connected():
                cursor = self.conn.cursor()
                try:
                    print(f"Executing query: {query} with params: {params} (called by: {caller})")
    
                    # Execute the query with or without parameters
                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)
    
                    result = None
    
                    # Fetch results if the query is a SELECT type
                    if cursor.with_rows:
                        print(f"Fetching results for query: {query}")
                        if fetchone:
                            result = cursor.fetchone()
                            print(f"Fetched one result: {result}")
                        else:
                            result = cursor.fetchall()
                            print(f"Fetched all results: {result}")
    
                    # Commit modifications for non-SELECT queries
                    self.conn.commit()
                    print(f"Query committed: {query}")
                    return result
    
                finally:
                    try:
                        cursor.close()
                        print(f"Cursor closed for query: {query}")
                    except errors.Error as close_cursor_error:
                        print(f"Error closing cursor: {close_cursor_error} for query: {query}")
    
        except (errors.InterfaceError, errors.OperationalError, errors.DatabaseError, TimeoutError, errors.ProgrammingError) as e:
            print(f"Error occurred: {e} (query: {query}, called by: {caller})")
            print("Attempting to reconnect to the database...")
            self.connect_to_database()
    
            # Retry the query after reconnecting
            if self.conn is not None and self.conn.is_connected():
                print("Reconnection successful. Retrying query...")
                return self.execute_query(query, params, fetchone, caller)
            else:
                print("Reconnection failed. Unable to retry the query.")
    
        except Exception as e:
            print(f"GeneralError: {e} (query: {query}, called by: {caller})")
    
        return None






        
    def log_error_in_db(self, error_message, error_type):
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Insert the error details into the Errors table
            self.execute_query(
                "INSERT INTO Errors (`Device IP`, `Device Name`, `Error`, `Error Raised Date`, `Error Status`) "
                "VALUES (%s, %s, %s, %s, %s)",
                (self.raspberry_id, self.device_name, f"{error_type}: {error_message}", current_time, 'Raised'),
                caller="log_error_in_db"
            )
            print(f"Error logged to database: {error_message}")
        except Exception as e:
            print(f"Failed to log error to database: {e}")    


    def show_login_page(self):
        self.main_page_frame.pack_forget()
        self.login_page_frame.pack(expand=True, fill='both')
        self.login_page_frame.logged_in = False
        self.login_page_frame.set_focus()

    def show_main_page(self):
        self.login_page_frame.pack_forget()
        self.main_page_frame.pack(expand=True, fill='both')

        raspberry_device = self.execute_query(
            "SELECT * FROM RaspberryDevices WHERE device_id=%s AND device_name=%s",
            (self.raspberry_id, self.device_name),
            fetchone=True,
            caller="show_main_page"
        )


        if raspberry_device:
            worker_id = self.get_worker_id()
            login_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if not self.check_worker_already_logged_in(worker_id):
                self.execute_query(
                    "INSERT INTO WorkerWorkstation (Worker_id, Workstation_ID, Raspberry_Device, Login_Date) VALUES (%s, %s, %s, %s)",
                    (worker_id, self.raspberry_id, self.device_name, login_date),
                    caller="show_main_page"
                )
                self.current_worker_id = worker_id
                self.main_page_frame.update_username()
                self.main_page_frame.entry.focus_set()
        else:
            print("Nem talÃ¡lhatÃ³ megfelelÅ‘ Raspberry eszkÃ¶z az adatbÃ¡zisban.")

    def get_worker_id(self):
        rfid = self.login_page_frame.entry.get()
        worker_id = self.execute_query(
            "SELECT id FROM Workers WHERE rfid_tag=%s",
            (rfid,),
            fetchone=True,
            caller="get_worker_id"
        )
        if worker_id:
            return worker_id[0]
        else:
            print("Nem talÃ¡lhatÃ³ megfelelÅ‘ munkÃ¡s azonosÃ­tÃ³ az adatbÃ¡zisban.")
            return None

    def check_worker_already_logged_in(self, worker_id):
        existing_record = self.execute_query(
            "SELECT * FROM WorkerWorkstation WHERE worker_id=%s AND Raspberry_Device=%s AND logout_date IS NULL",
            (worker_id, self.raspberry_id),
            fetchone=True,
            caller="check_worker_already_logged_in"
        )
        if existing_record:
            print(f"[DEBUG] Active session found for worker_id={worker_id} on device={self.raspberry_id}")
        else:
            print(f"[DEBUG] No active session found for worker_id={worker_id} on device={self.raspberry_id}")
        return existing_record is not None

    def show_logout_page(self):
        active_login = self.execute_query(
            "SELECT * FROM WorkerWorkstation WHERE logout_date IS NULL",
            fetchone=True,
            caller="show_logout_page"
        )

        if active_login:
            self.main_page_frame.pack_forget()
            self.main_page_frame.pack(expand=True, fill='both')
            self.main_page_frame.entry.focus_set()
        else:
            print("Nincs aktÃ­v bejelentkezÃ©s.")

    def logout(self):
        affected_rows = self.execute_query(
            "UPDATE WorkerWorkstation SET logout_date=%s WHERE logout_date IS NULL",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),),
            caller="logout"
        )

        if affected_rows == 0:
            print("No rows were updated. Ensure that there are records with logout_date IS NULL.")
        else:
            print(f"{affected_rows} row(s) updated successfully.")
        self.show_login_page()
        self.login_page_frame.entry.delete(0, tk.END)





class LoginPage(ttk.Frame):

    def __init__(self, master):
        super().__init__(master)
        self.label = ttk.Label(self, text="Prihlasovacia stránka", font=("Helvetica", 50))
        self.label.pack(padx=10, pady=20)
        
        self.label2 = ttk.Label(self, text="Prosím, naskenujte svoju kartu", font=("Helvetica", 25))
        self.label2.pack(padx=10, pady=100)

        self.entry = ttk.Entry(self, width=50, font=("Helvetica", 20))
        self.entry.pack(padx=20, pady=20)
        self.entry.bind("<KeyRelease>", self.check_rfid)

        self.logged_in = False

        self.shift_characters = {
            '/': '-'
        }

        image = Image.open("logo.png")
        image = image.resize((500, 250))
        self.logo_image = ImageTk.PhotoImage(image)

        self.logo = tk.Label(self, image=self.logo_image, background="white")
        self.logo.pack(side=tk.BOTTOM, pady=10)
        
    def convert_to_slovak(self, text):
        converted_text = ""
        for char in text:
            if char in self.shift_characters:
                converted_text += self.shift_characters[char]
            else:
                converted_text += char
        return converted_text

    def check_rfid(self, event):
        self.after(200, self.search_worker)
        current_text = self.entry.get()
        converted_text = self.convert_to_slovak(current_text)
        self.entry.delete(0, tk.END)
        self.entry.insert(0, converted_text)

    def search_worker(self):
        rfid = self.entry.get().strip()
        worker = self.master.execute_query(
            "SELECT * FROM Workers WHERE rfid_tag=%s", (rfid,), fetchone=True, caller="search_worker"

        )

        if worker and not self.logged_in:
            self.logged_in = True
            self.master.show_main_page()

    def set_focus(self):
        self.entry.focus_set()


class MainPage(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.label = ttk.Label(self, text="Stránka na skenovanie WO", font=("Helvetica", 50))
        self.label.pack(padx=10, pady=10)

        self.username_label = ttk.Label(self, text="Používateľ prihlásený ako: ", font=("Helvetica", 20))
        self.username_label.pack(padx=10, pady=5)

        self.entry = ttk.Entry(self, width=30, font=("Helvetica", 20))
        self.entry.pack(padx=20, pady=20)

        self.text_box = tk.Text(self, width=50, height=8, font=("Helvetica", 30))
        self.text_box.pack(padx=10, pady=5)
        self.text_box.bind("<Return>", self.set_text_size)
        self.text_box.delete(1.0, tk.END)
        self.text_box.insert(tk.END, f"Prosím, najprv naskenujte TOP LEVEL QR kód.\nAk je TOP LEVEL QR kód naskenovaný,\nnaskenujte iný QR kód.")

        self.logout_button = ttk.Button(self, text="Logout", command=self.master.logout)
        #self.logout_button.pack(padx=10, pady=10)
        
        image = Image.open("logo.png")
        image = image.resize((400, 200))
        self.logo_image = ImageTk.PhotoImage(image)

        self.logo = tk.Label(self, image=self.logo_image, background="white")
        self.logo.pack(side=tk.BOTTOM, pady=10)

        self.entry.bind("<KeyRelease>", self.read_qr_code)

        self.main_work_order = None
        self.wo_value = None

        self.conn = None  # InicializÃ¡ld az adatbÃ¡zis-kapcsolatot
        self.connect_to_database()  # Hozd lÃ©tre a kapcsolatot a program indulÃ¡sakor

    def connect_to_database(self):
        """Establishes a connection to the database."""
        try:
            self.conn = mysql.connector.connect(
                host='10.10.2.15',
                database='paperless',
                user='root',
                password='admin321',
                connection_timeout=10
            )
            if self.conn.is_connected():
                print("Successfully connected to the database.")
        except mysql.connector.Error as e:
            print(f"Error connecting to the database: {e}")
            self.conn = None 

    def set_text_size(self, event):
        self.text_box.config(font=("Helvetica", 50))    

    def read_qr_code(self, event):
        if event.keysym == "Return":
            qr_code_text = self.entry.get().strip()
            print(f"Original text: {qr_code_text}")  # Debugging statement
            
            # Check for specific prefixes and replace them
            if qr_code_text.startswith("STATION/"):
                qr_code_text = qr_code_text.replace("STATION/", "STATION-", 1)
            elif qr_code_text.startswith("PROCESS/"):
                qr_code_text = qr_code_text.replace("PROCESS/", "PROCESS-", 1)

            print(f"Processed text: {qr_code_text}")  # Debugging statement
            
            if qr_code_text.lower() == "calibrate":
                print("Calibration triggered")  # Debugging statement
                self.calibrate_ui()
            elif qr_code_text.lower() == "logout":
                print("User logged out")  # Debugging statement
                self.entry.delete(0, tk.END)
                self.master.logout()   
            else:
                self.process_qr_code(qr_code_text)


    def calibrate_ui(self):
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        
        print(f"Screen size: {screen_width}x{screen_height}")  # Debugging statement

        # Alapértelmezett arányok (1920x1080 referenciafelbontás alapján)
        base_width = 1920
        base_height = 1080
        scale_x = screen_width / base_width
        scale_y = screen_height / base_height
        scale = min(scale_x, scale_y)  # Az elemek arányos nagyításához

        # Dinamikus betűméret kiszámítása
        label_font_size = int(50 * scale)
        username_font_size = int(20 * scale)
        entry_font_size = int(20 * scale)
        text_box_font_size = int(30 * scale)
        logo_size = (int(400 * scale), int(200 * scale))

        # UI elemek méretezése
        self.label.config(font=("Helvetica", label_font_size))
        self.username_label.config(font=("Helvetica", username_font_size))
        self.entry.config(font=("Helvetica", entry_font_size), width=int(30 * scale))

        self.text_box.config(font=("Helvetica", text_box_font_size), width=int(40 * scale), height=int(8 * scale))

        # Logo újraméretezése
        if hasattr(self, 'logo_image') and self.logo_image:
            original_logo = Image.open("logo.png")
            resized_logo = original_logo.resize(logo_size, Image.Resampling.LANCZOS)
            self.logo_image = ImageTk.PhotoImage(resized_logo)
            self.logo.config(image=self.logo_image)

        # UI frissítése
        self.update_idletasks()

        # Elemelrendezés
        padding_x = int(10 * scale)
        padding_y = int(10 * scale)
        self.label.pack_configure(padx=padding_x, pady=padding_y)
        self.username_label.pack_configure(padx=padding_x, pady=int(5 * scale))
        self.entry.pack_configure(padx=padding_x, pady=int(20 * scale))
        self.text_box.pack_configure(padx=padding_x, pady=int(10 * scale))
        self.logout_button.pack_configure(padx=padding_x, pady=int(10 * scale))
        self.logo.pack_configure(side=tk.BOTTOM, pady=int(10 * scale))

        print("UI calibrated successfully.")


    def process_qr_code(self, qr_code_text):
        if qr_code_text.startswith("WO"):
            self.handle_work_order_qr(qr_code_text)
        elif qr_code_text.startswith("PROCESS"):
            self.handle_process_qr(qr_code_text)
        elif qr_code_text.startswith("STATION"):
            self.handle_station_qr(qr_code_text)
        else:
            self.text_box.delete(1.0, tk.END)
        self.entry.delete(0, tk.END)
        self.entry.focus_set()

    def handle_work_order_qr(self, qr_code_text):
        data = qr_code_text.split("|")
        wo_data = {item.split("-")[0]: "-".join(item.split("-")[1:]) for item in data if "-" in item}

        self.wo_value = wo_data.get("WO", "").strip()
        pn_value = wo_data.get("PN", "").strip()
        master_pn_value = wo_data.get("MASTER_PN", "").strip()
        
        hierarchy_key = next((key for key in wo_data.keys() if key.startswith("HIERARCHY")), None)
        hierarchy = wo_data.get(hierarchy_key, "").strip() if hierarchy_key else ""
        print(f"Handling WO: {self.wo_value}, PN: {pn_value}, MASTER_PN: {master_pn_value}, HIERARCHY: {hierarchy}")

        if master_pn_value == pn_value:
            pn_value = master_pn_value
        self.start_or_complete_work_order(self.wo_value, pn_value, master_pn_value, hierarchy)




    def start_or_complete_work_order(self, wo_value, pn_value, master_pn_value, hierarchy):
        sub1_value = None
        sub2_value = None

        # Ellenőrizd az adatbázis-kapcsolatot
        if not self.master.ensure_connection():
            print("Nincs aktív adatbázis-kapcsolat. Nem lehet folytatni a műveletet.")
            return

        if hierarchy:
            # Használj regex-et az értékek kinyeréséhez
            pn_match = re.search(r'PN:\s*(\S+)', hierarchy)
            if pn_match:
                pn_value = pn_match.group(1)

            sub1_match = re.search(r'SUB1:\s*(\S+)', hierarchy)
            if sub1_match:
                sub1_value = sub1_match.group(1)

            sub2_match = re.search(r'SUB2:\s*(\S+)', hierarchy)
            if sub2_match:
                sub2_value = sub2_match.group(1)

            print(f"Hierarchy:\nPN: {pn_value}\nSUB1: {sub1_value}\nSUB2: {sub2_value}")

            try:
                if sub2_value:
                    print(f"SUB2: {sub2_value}")
                    sub2_result = self.master.execute_query(
                        "SELECT ID FROM Workorders WHERE PN=%s AND WO=%s AND HIERARCHY LIKE %s",
                        (sub2_value, wo_value, f"{hierarchy}"),
                        fetchone=True,
                        caller="start_or_complete_work_order"
                    )

                    if sub2_result:
                        sub2_workid = sub2_result[0]
                        print(f"SUB2 ID: {sub2_workid}")

                        if self.is_work_order_active(sub2_workid):
                            self.complete_work_order(sub2_workid, hierarchy)
                            return True
                        else:
                            self.start_work_order(sub2_workid, hierarchy)
                    else:
                        print("No matching SUB2 found.")

                elif sub2_value is None:
                    print("SUB2 none")
                    sub1_result = self.master.execute_query(
                        "SELECT ID FROM Workorders WHERE PN=%s AND WO=%s AND HIERARCHY LIKE %s",
                        (sub1_value, wo_value, f"{hierarchy}"),
                        fetchone=True,
                        caller="start_or_complete_work_order"
                    )

                    if sub1_result:
                        sub1_workid = sub1_result[0]
                        print(f"SUB1 ID: {sub1_workid}")

                        if self.is_work_order_active(sub1_workid):
                            self.complete_work_order(sub1_workid, hierarchy)
                            return True
                        else:
                            self.start_work_order(sub1_workid, hierarchy)
                    else:
                        print("No matching SUB1 found.")
                        pn_result = self.master.execute_query(
                            "SELECT ID FROM Workorders WHERE PN=%s AND WO=%s AND master_pn=%s",
                            (pn_value, wo_value, master_pn_value),
                            fetchone=True,
                            caller="start_or_complete_work_order"
                        )

                        if pn_result:
                            pn_id = pn_result[0]
                            print(f"PN value ID: {pn_id}")

                            if self.is_work_order_active(pn_id):
                                self.complete_work_order(pn_id, hierarchy)
                                return True
                            else:
                                self.start_work_order(pn_id, hierarchy)
                        else:
                            print("No matching PN found.")
            except mysql.connector.Error as e:
                print(f"Database error: {e}")
                self.master.ensure_connection()  # Újracsatlakozás

        else:
            print(f"Hierarchy: {hierarchy}")

            try:
                if pn_value == master_pn_value:
                    hierarchy = f"PN: {pn_value}"
                    print("Master PN == PN value")
                    pn_result = self.master.execute_query(
                        "SELECT ID FROM Workorders WHERE PN=%s AND WO=%s AND master_pn=%s",
                        (pn_value, wo_value, master_pn_value),
                        fetchone=True,
                        caller="start_or_complete_work_order"
                    )

                    if pn_result:
                        pn_id = pn_result[0]
                        print(f"PN value ID: {pn_id}")

                        if self.is_work_order_active(pn_id):
                            self.complete_work_order(pn_id, hierarchy)
                        else:
                            self.start_work_order(pn_id, hierarchy)
                    else:
                        print("No matching PN found.")
            except mysql.connector.Error as e:
                print(f"Database error: {e}")
                self.master.ensure_connection()  # Újracsatlakozás




    







    





    def extract_value(self, hierarchy, start_str, end_str):
        start_idx = hierarchy.find(start_str)
        if start_idx == -1:
            return None
        start_idx += len(start_str)
        if end_str:
            end_idx = hierarchy.find(end_str, start_idx)
            if end_idx == -1:
                return hierarchy[start_idx:].strip()
            return hierarchy[start_idx:end_idx].strip()
        return hierarchy[start_idx:].strip()

    def is_work_order_active(self, work_order_id):
        status_result = self.master.execute_query(
            "SELECT status FROM WorkstationWorkorder WHERE work_id=%s AND status = 'Active'",
            (work_order_id,), fetchone=True, caller="is_work_order_active"
        )
        if status_result and status_result[0] == 'Active':
            print("Work order Active")
            return True
        else:
            print("Work order not Active")
            return False

    def start_work_order(self, work_order_id, hierarchy):
        print("Start work order")
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.master.execute_query(
            "INSERT INTO WorkstationWorkorder (workstation_id, device_id, worker_id, work_id, start_time, status) VALUES (%s, %s, %s, %s, %s, %s)",
            (self.master.raspberry_id, self.master.device_name, self.master.current_worker_id, work_order_id, start_time, 'Active'),
            caller="start_work_order"
        )
        self.master.current_work_order_id = work_order_id
        print("Start Eddig")
        result = self.master.execute_query(
            "SELECT WO, QTY, ECN, REV FROM Workorders WHERE ID=%s",
            (work_order_id,), fetchone=True, caller="start_work_order"
        )
        if result:
            wo_value, qty_value, ecn_value, rev_value = result
            self.text_box.delete(1.0, tk.END)
            self.text_box.insert(tk.END, f"WO {wo_value} začínal.\nWO data: \n{hierarchy}\nECN: {ecn_value}\nQT: {qty_value}\nREV: {rev_value}\nProsím, naskenujte STATION-QR kód.")
            print(f"WO {work_order_id} started.")

    def complete_work_order(self, work_order_id, hierarchy):
        # Első felugró ablak a munkafolyamat befejezésének megerősítésére
        confirm_window = tk.Toplevel(self)
        confirm_window.title("Dokončenie pracovného procesu")
        confirm_window.transient(self)
        confirm_window.grab_set()
        confirm_window.focus_set()

        # Üzenet a felugró ablakban
        message_label = ttk.Label(confirm_window, text="Si istý, že chcete dokončiť tento pracovný proces?")
        message_label.pack(padx=20, pady=20)

        # Igen gomb
        def confirm():
            confirm_window.destroy()  # Felugró ablak bezárása

            # Második felugró ablak a darabszám megadásához
            qty_window = tk.Toplevel(self)
            qty_window.title("Zadajte množstvo")
            qty_window.transient(self)
            qty_window.grab_set()

            qty_message_label = ttk.Label(qty_window, text="Koľko kusov posielate?")
            qty_message_label.pack(padx=20, pady=10)

            qty_entry = ttk.Entry(qty_window, width=10)
            qty_entry.pack(padx=20, pady=10)
            qty_window.after(100, qty_entry.focus_set)  # Az ablak megjelenése után biztosítjuk a fókuszt

            def submit_qty(event=None):
                qty_value = qty_entry.get().strip()
                if not qty_value.isdigit() or int(qty_value) <= 0:
                    messagebox.showerror("Neplatný množstvo", "Prosím, zadajte platné množstvo!")
                    return

                self.qty_value = qty_value  # Osztályszintű változóban tároljuk el a qty_value értéket
                qty_window.destroy()  # Bezárjuk a darabszám megadása ablakot

                # Harmadik felugró ablak a darabszám megerősítésére
                confirm_qty_window = tk.Toplevel(self)
                confirm_qty_window.title("Potvrdenie množstva")
                confirm_qty_window.transient(self)
                confirm_qty_window.grab_set()
                
                # Az ablak megjelenése után fókusz erőltetése
                confirm_qty_window.after(100, confirm_qty_window.focus_force)
                

                qty_confirm_message_label = ttk.Label(
                    confirm_qty_window,
                    text=f"Si istý, že si dokončil {self.qty_value} kusov?"
                )
                qty_confirm_message_label.pack(padx=20, pady=20)

                # Igen gomb a darabszám megerősítésére
                def confirm_qty():
                    confirm_qty_window.destroy()  # FelugrÃ³ ablak bezÃ¡rÃ¡sa

                    # KÃ¼ldjÃ¼k el a darabszÃ¡mot az adatbÃ¡zisba, Ã©s fejezzÃ¼k be a munkafolyamatot
                    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # Update the WorkstationWorkorder table with status, end time, and qty
                    self.master.execute_query(
                        "UPDATE WorkstationWorkorder SET status='Completed', end_time=%s, QTY=%s WHERE work_id=%s AND status='Active'",
                        (end_time, self.qty_value, work_order_id), caller="complete_work_order"
                    )

                    print("Completed eddig 2")

                    # Fetch work order details
                    result = self.master.execute_query(
                        "SELECT WO, QTY, ECN, REV FROM Workorders WHERE ID=%s",
                        (work_order_id,), fetchone=True, caller="complete_work_order"
                    )
                    if result:
                        wo_value, qty_value, ecn_value, rev_value = result
                        self.text_box.delete(1.0, tk.END)
                        self.text_box.insert(tk.END, f"WO {wo_value} dokončené.\nÚdaje o WO data: \n{hierarchy}\nECN: {ecn_value}\nQT: {qty_value}\nREV: {rev_value}\nNaskenujte nový QR kód alebo naskenujte \nPROCESS-QR kód, ak ste zabudli.")
                        print(f"WO {work_order_id} completed.")

                    self.check_after_complete(work_order_id)

                # Nem gomb a darabszám elvetésére
                def cancel_qty():
                    confirm_qty_window.destroy()  # Felugró ablak bezárása

                # Gombok létrehozása
                yes_button_qty = ttk.Button(confirm_qty_window, text="Áno (1)", command=confirm_qty)
                yes_button_qty.pack(side=tk.LEFT, padx=10, pady=10)

                no_button_qty = ttk.Button(confirm_qty_window, text="Nie (3)", command=cancel_qty)
                no_button_qty.pack(side=tk.RIGHT, padx=10, pady=10)

                # Billentyűkötés a felugró ablakhoz
                def qty_key_handler(event):
                    if event.char == '1':
                        confirm_qty()
                    elif event.char == '3':
                        cancel_qty()

                confirm_qty_window.bind("<Key>", qty_key_handler)
                confirm_qty_window.after(100, confirm_qty_window.focus_set)  # Az ablak megjelenése után biztosítjuk a fókuszt

            qty_entry.bind("<Return>", submit_qty)
            qty_entry.bind("<KP_Enter>", submit_qty)  # Jobb oldali numerikus pad 'Enter' esemény

        # Nem gomb
        def cancel():
            confirm_window.destroy()  # Felugró ablak bezárása

        # Igen gomb létrehozása
        yes_button = ttk.Button(confirm_window, text="Áno (1)", command=confirm)
        yes_button.pack(side=tk.LEFT, padx=10, pady=10)

        # Nem gomb létrehozása
        no_button = ttk.Button(confirm_window, text="Nie (3)", command=cancel)
        no_button.pack(side=tk.RIGHT, padx=10, pady=10)

        # Billentyűkötés a felugró ablakhoz
        def key_handler(event):
            if event.char == '1':
                confirm()
            elif event.char == '3':
                cancel()

        confirm_window.bind("<Key>", key_handler)


        confirm_window.transient(self)  # Az ablakot a főablak fölé helyezi
        confirm_window.grab_set()  # Blokkolja a főablakot, amíg a felugró ablak nyitva van
        confirm_window.focus_set()  # Fókusz az ablakra
        self.wait_window(confirm_window)  # Várakozás a felugró ablak bezárásáig








    def check_after_complete(self, work_order_id):
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Log the work order ID
        print(f"WorkOrder ID: {work_order_id}")
        
        # Fetch WO and MASTER_PN
        wo_masterpn = self.master.execute_query(
            "SELECT WO, MASTER_PN FROM WORKORDERS WHERE ID=%s",
            (work_order_id,), caller="check_after_complete"
        )
        print(f"WO and MASTER_PN fetched: {wo_masterpn}")

        if not wo_masterpn:
            print("No matching records found in WORKORDERS.")
            return
        
        wo, master_pn = wo_masterpn[0][0], wo_masterpn[0][1]
        print(f"WO: {wo}, MASTER_PN: {master_pn}")
        
        # Fetch all work_id and process_id from WORKSTATIONWORKORDER
        workstation_ids = self.master.execute_query(
            "SELECT work_id, process_id FROM WORKSTATIONWORKORDER",
            caller="check_after_complete"
        )
        print(f"Fetched workstation IDs: {workstation_ids}")

        # Create a set of work_ids for quick lookup
        workstation_id_set = {int(row[0]) for row in workstation_ids}
        print(f"Workstation ID set: {workstation_id_set}")

        # Check for missing IDs
        missing_ids = [wo_id for wo_id in [work_order_id] if wo_id not in workstation_id_set]
        print(f"Missing IDs: {missing_ids}")

        if not missing_ids:
            # Check if all process_id values are 'TEST'
            all_processes_test = all(row[1] == 'QC' for row in workstation_ids if int(row[0]) == work_order_id)
            print(f"All processes are 'QC': {all_processes_test}")
            
            if all_processes_test:
                # Fetch matching records from WORKORDERS
                matching_records = self.master.execute_query(
                    "SELECT ID FROM WORKORDERS WHERE WO=%s AND MASTER_PN=%s AND PN=%s",
                    (wo, master_pn, master_pn), caller="check_after_complete"
                )
                print(f"Matching records in WORKORDERS: {matching_records}")

                if matching_records:
                    # Ha van talÃ¡lat, frissÃ­tjÃ¼k a WORKSTATIONWORKORDER tÃ¡blÃ¡ban a megfelelÅ‘ rekordot
                    matching_id = matching_records[0][0]
                    self.master.execute_query(
                        "UPDATE WORKSTATIONWORKORDER SET status='Completed' AND end_time=%s WHERE work_id=%s",
                        (end_time,matching_id,), caller="check_after_complete"
                    )
                    print("A WORKSTATIONWORKORDER tÃ¡bla frissÃ­tve lett a 'Completed' stÃ¡tuszra.")
                else:
                    print("Nem talÃ¡lhatÃ³ megfelelÅ‘ rekord a WORKORDERS tÃ¡blÃ¡ban.")
            else:
                print("Minden ID szerepel a WORKSTATIONWORKORDER tÃ¡blÃ¡ban, de nem minden process_id Ã©rtÃ©ke 'QC'.")
        else:
            print("Nem minden ID szerepel a WORKSTATIONWORKORDER tÃ¡blÃ¡ban. HiÃ¡nyzÃ³ ID-k:", missing_ids)

    def handle_process_qr(self, qr_code_text):
        data = qr_code_text.split("|")
        process_data = {item.split("-")[0]: item.split("-")[1] for item in data if "-" in item}
        if "PROCESS" in process_data and self.master.current_work_order_id:
            # Check if process_id is not set for the current work order
            process_check = self.master.execute_query(
                "SELECT process_id FROM WorkstationWorkorder WHERE work_id=%s AND status=%s",
                (self.master.current_work_order_id, "Active"), fetchone=True, caller="handle_process_qr"
            )
            print("Process check: ", process_check)
            if process_check[0] == '' or process_check[0] == 'N/A':
                self.text_box.delete(1.0, tk.END)
                self.text_box.insert(tk.END, "Najprv musíte skenovať STATION-QR.")
                return

            process_id = process_data.get("PROCESS", "")
            self.master.execute_query(
                "UPDATE WorkstationWorkorder SET next_station_id=%s WHERE work_id=%s AND status=%s",
                (process_id, self.master.current_work_order_id, "Active"), caller="handle_process_qr"
            )
            data = self.master.execute_query(
                "SELECT WO, PN, HIERARCHY FROM WORKORDERS WHERE ID=%s",
                (self.master.current_work_order_id,), fetchone=True, caller="handle_process_qr"
            )
            if data:
                wo, pn, hierarchy = data
                if hierarchy == "N/A":
                    hierarchy = ''
                self.text_box.delete(1.0, tk.END)
                self.text_box.insert(tk.END, f"WO: {wo}\nPN: {pn}\n{hierarchy}\nNaskenujte znova ten isty QR kod pre dokoncenie Part Number.")


    def handle_station_qr(self, qr_code_text):
        data = qr_code_text.split("|")
        station_data = {item.split("-")[0]: item.split("-")[1] for item in data if "-" in item}
        if "STATION" in station_data and self.master.current_work_order_id:
            station = station_data.get("STATION", "")
            self.master.execute_query(
                "UPDATE WorkstationWorkorder SET process_id=%s WHERE work_id=%s AND status=%s",
                (station, self.master.current_work_order_id, "Active"), caller="handle_station_qr"
            )
            data = self.master.execute_query(
                "SELECT WO, PN, HIERARCHY FROM WORKORDERS WHERE ID=%s",
                (self.master.current_work_order_id,), fetchone=True, caller="handle_station_qr"
            )

            if data:
                wo, pn, hierarchy = data
                if hierarchy == "N/A":
                    hierarchy = ''
                self.text_box.delete(1.0, tk.END)
                self.text_box.insert(tk.END, f"WO: {wo}\nPN: {pn}\n{hierarchy}\nPoslane na novu stanicu {station}.\nProsim, naskenujte PROCESS-QR kod.")


    def update_username(self):
        worker_id = self.master.current_worker_id
        worker = self.master.execute_query(
            "SELECT name FROM Workers WHERE id=%s",
            (worker_id,), fetchone=True, caller="update_username"
        )
        if worker:
            self.username_label.config(text=f"Používatel prihlásené ako: {worker[0]}")

    def set_focus(self):
        self.entry.focus_set()



if __name__=="__main__":
    app = RaspberryApp()
    app.mainloop()
