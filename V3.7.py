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

from datetime import datetime
from PIL import Image, ImageTk
import re
import socket
import netifaces as ni




class RaspberryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.style = Style('cyborg')
        self.title("Raspberry App")
        self.attributes('-zoomed', True)
        # Initialize connection
        self.conn = self.connect_to_database()
        if self.conn:
            self.cursor = self.conn.cursor()

        self.login_page_frame = LoginPage(self)
        self.main_page_frame = MainPage(self)

        self.show_login_page()
        self.login_page_frame.set_focus()

        self.device_name = socket.gethostname()
        self.raspberry_id = socket.gethostbyname(self.device_name)
        self.workstation_id = "2"
        # WiFi interfÃƒÂ©sz (wlan0) IP cÃƒÂ­mÃƒÂ©nek lekÃƒÂ©rdezÃƒÂ©se
        wifi_interface = 'wlan0'
        try:
            ip_address = ni.ifaddresses(wifi_interface)[ni.AF_INET][0]['addr']
        except KeyError:
            ip_address = 'Nincs WiFi kapcsolat vagy az interfÃƒÂ©sz nem elÃƒÂ©rhetÃ…â€˜'
        self.raspberry_id  = ip_address    
        print("Device name: ", self.device_name)
        print("Raspberry id: " , self.raspberry_id)
        print(f"WiFi IP address: {ip_address}")

        self.current_worker_id = None
        self.current_work_order_id = None

    def connect_to_database(self):
        """Establishes a connection to the MySQL database."""
        try:
            # Connect to the MySQL database
            connection = mysql.connector.connect(
                host='10.10.2.15',
                database='paperless',
                user='root',
                password='admin321',
                connection_timeout=120  # Set a timeout for the connection
            )
            if connection.is_connected():
                print("Successful connection to the database.")
                self.conn = connection  # Update self.conn with the new connection
                return connection
        except Error as e:
            print(f"Error while connecting to the database: {e}")
            return None
    
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
            print("Nem található megfelelő Raspberry eszköz az adatbázisban.")

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
            print("Nem található megfelelő munkás azonosító az adatbázisban.")
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
            print("Nincs aktív bejelentkezés.")

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
            '+': '1', 'ľ': '2', 'š': '3', 'č': '4', 'ť': '5',
            'ž': '6', 'ý': '7', 'á': '8', 'í': '9', 'é': '0',
            '=': '-', '%': '=', 'Q': 'q', 'W': 'w', 'E': 'e',
            'R': 'r', 'T': 't', 'Z': 'z', 'U': 'u', 'I': 'i',
            'O': 'o', 'P': 'p', 'ú': '[', 'ä': ']', 'ň': '\\',
            'A': 'a', 'S': 's', 'D': 'd', 'F': 'f', 'G': 'g',
            'H': 'h', 'J': 'j', 'K': 'k', 'L': 'l', 'ô': ';',
            '§': "'", 'Y': 'y', 'X': 'x', 'C': 'c', 'V': 'v',
            'B': 'b', 'N': 'n', 'M': 'm', '?': ',', ':': '.',
            '_': '/', 'ˇ': '`', '!': '1', '"': '2', '§': '3',
            '$': '4', '%': '5', '/': '6', '&': '7', '(': '8',
            ')': '9', '=': '0', '_': '-'
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

        self.conn = None  # Inicializáld az adatbázis-kapcsolatot
        self.connect_to_database()  # Hozd létre a kapcsolatot a program indulásakor

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
            print(f"Entered text: {qr_code_text}")  # Debugging statement
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

        # Example adjustments based on screen size
        if screen_width > 1920:
            self.label.config(font=("Helvetica", 70))
            self.username_label.config(font=("Helvetica", 30))
            self.entry.config(font=("Helvetica", 30), width=40)
            self.text_box.config(font=("Helvetica", 40), width=50, height=10)
        else:
            self.label.config(font=("Helvetica", 50))
            self.username_label.config(font=("Helvetica", 20))
            self.entry.config(font=("Helvetica", 20), width=30)
            self.text_box.config(font=("Helvetica", 30), width=40, height=8)

        # Force a UI update
        self.update_idletasks()
        self.master.update_idletasks()

        # Redefine the layout to ensure the changes take effect
        self.label.pack_configure(padx=10, pady=10)
        self.username_label.pack_configure(padx=10, pady=5)
        self.entry.pack_configure(padx=20, pady=20)
        self.text_box.pack_configure(padx=10, pady=5)
        self.logout_button.pack_configure(padx=10, pady=10)
        self.logo.pack_configure(side=tk.BOTTOM, pady=10)

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
    
        if hierarchy:
            # Use regex to find PN, SUB1, and SUB2
            pn_match = re.search(r'PN:\s*(\S+)', hierarchy)
            if pn_match:
                pn_value = pn_match.group(1)
    
            sub1_match = re.search(r'SUB1:\s*(\S+)', hierarchy)
            if sub1_match:
                sub1_value = sub1_match.group(1)
    
            sub2_match = re.search(r'SUB2:\s*(\S+)', hierarchy)
            if sub2_match:
                sub2_value = sub2_match.group(1)
    
            print(f"Hierarchy: \nPN: {pn_value}\nSUB1: {sub1_value}\nSUB2: {sub2_value}")
    
            try:
                self.ensure_connection()  # Ensure connection is valid before any query
    
                if sub2_value:
                    print(f"SUB2: {sub2_value}")
                    cursor = self.conn.cursor()
                    cursor.execute("SELECT ID FROM Workorders WHERE PN=%s AND WO=%s AND HIERARCHY LIKE %s", (sub2_value, wo_value, f"{hierarchy}"))
                    sub2_result = cursor.fetchone()
                    cursor.close()
    
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
                    cursor = self.conn.cursor()
                    cursor.execute("SELECT ID FROM Workorders WHERE PN=%s AND WO=%s AND HIERARCHY LIKE %s", (sub1_value, wo_value, f"{hierarchy}"))
                    sub1_result = cursor.fetchone()
                    cursor.close()
    
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
                        cursor = self.conn.cursor()
                        cursor.execute("SELECT ID FROM Workorders WHERE PN=%s AND WO=%s AND master_pn=%s", (pn_value, wo_value, master_pn_value))
                        pn_result = cursor.fetchone()
                        cursor.close()
    
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
                # Handle reconnection and possibly retry query
                self.connect_to_database()
    
        else:
            print(f"Hierarchy: {hierarchy}")
    
            try:
                self.ensure_connection()
                if pn_value == master_pn_value:
                    hierarchy = f"PN: {pn_value}"
                    print("Master PN == PN value")
                    cursor = self.conn.cursor()
                    cursor.execute("SELECT ID FROM Workorders WHERE PN=%s AND WO=%s AND master_pn=%s", (pn_value, wo_value, master_pn_value))
                    pn_result = cursor.fetchone()
                    cursor.close()
    
                    if pn_result:
                        pn_id = pn_result[0]
                        print(f"PN value ID: {pn_id}")
    
                        if self.is_work_order_active(pn_id):
                            print("ITT MEG JO")
                            cursor = self.conn.cursor()
                            cursor.execute("SELECT COUNT(*) FROM Workorders WHERE master_pn=%s AND WO=%s", (master_pn_value, wo_value))
                            result = cursor.fetchone()
                            cursor.close()
    
                            print(f"Result: {result}")
    
                            if result and result[0] > 1:
                                self.text_box.delete(1.0, tk.END)
                                self.text_box.insert(tk.END, f"TOP LEVEL QR kód bol už naskenovaný.\nProsím, naskenujte iný SUB QR kód.\nDetaily: \nWO: {wo_value}\nPN: {pn_value}")
                                return False
                            else:
                                self.complete_work_order(pn_id, hierarchy)
                        else:
                            self.start_work_order(pn_id, hierarchy)
                    else:
                        print("No matching PN found.")
    
                elif pn_value != master_pn_value:
                    print("PN value != Master PN")
                    hierarchy = f"PN: {pn_value}"
                    cursor = self.conn.cursor()
                    cursor.execute("SELECT ID FROM Workorders WHERE PN=%s AND WO=%s AND master_pn=%s", (pn_value, wo_value, master_pn_value))
                    pn_result = cursor.fetchone()
                    cursor.close()
    
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
                self.connect_to_database()
    
    def ensure_connection(self):
        """Ensures that the database connection is active."""
        if self.conn is None or not self.conn.is_connected():
            print("Reconnecting to the database...")
            self.connect_to_database()



    





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
            self.text_box.insert(tk.END, f"WO {wo_value} started.\nWO data: \n{hierarchy}\nECN: {ecn_value}\nQT: {qty_value}\nREV: {rev_value}\nProsím, naskenujte STATION-QR kód.")
            print(f"WO {work_order_id} started.")

    def complete_work_order(self, work_order_id, hierarchy):
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("Completed eddig 1")
        
        # Update the WorkstationWorkorder table
        self.master.execute_query(
            "UPDATE WorkstationWorkorder SET status='Completed', end_time=%s WHERE work_id=%s AND status='Active'",
            (end_time, work_order_id), caller="complete_work_order"
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
            self.text_box.insert(tk.END, f"WO {wo_value} completed.\nWO data: \n{hierarchy}\nECN: {ecn_value}\nQTY: {qty_value}\nREV: {rev_value}\nNaskenujte nový QR kód alebo naskenujte \nPROCESS-QR kód, ak ste zabudli.")
            print(f"WO {work_order_id} completed.")
        
        self.check_after_complete(work_order_id)

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
            all_processes_test = all(row[1] == 'TEST' for row in workstation_ids if int(row[0]) == work_order_id)
            print(f"All processes are 'TEST': {all_processes_test}")
            
            if all_processes_test:
                # Fetch matching records from WORKORDERS
                matching_records = self.master.execute_query(
                    "SELECT ID FROM WORKORDERS WHERE WO=%s AND MASTER_PN=%s AND PN=%s",
                    (wo, master_pn, master_pn), caller="check_after_complete"
                )
                print(f"Matching records in WORKORDERS: {matching_records}")

                if matching_records:
                    # Ha van találat, frissítjük a WORKSTATIONWORKORDER táblában a megfelelő rekordot
                    matching_id = matching_records[0][0]
                    self.master.execute_query(
                        "UPDATE WORKSTATIONWORKORDER SET status='Completed' AND end_time=%s WHERE work_id=%s",
                        (end_time,matching_id,), caller="check_after_complete"
                    )
                    print("A WORKSTATIONWORKORDER tábla frissítve lett a 'Completed' státuszra.")
                else:
                    print("Nem található megfelelő rekord a WORKORDERS táblában.")
            else:
                print("Minden ID szerepel a WORKSTATIONWORKORDER táblában, de nem minden process_id értéke 'TEST'.")
        else:
            print("Nem minden ID szerepel a WORKSTATIONWORKORDER táblában. Hiányzó ID-k:", missing_ids)

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
                self.text_box.insert(tk.END, "Najprv musÃ­Å¡ skenovaÅ¥ STATION-QR.")
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
            self.username_label.config(text=f"Používateľ prihlásený ako: {worker[0]}")

    def set_focus(self):
        self.entry.focus_set()




if __name__=="__main__":
    app = RaspberryApp()
    app.mainloop()

