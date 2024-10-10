# importok és os beállítások...
import os
if os.environ.get('DISPLAY', '') == '':
    print('no display found. Using :0.0')
    os.environ.__setitem__('DISPLAY', ':0.0')
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from ttkbootstrap import Style
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from PIL import Image, ImageTk

class RaspberryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.style = Style('cyborg')
        self.title("Raspberry App")
        self.attributes('-zoomed', True)

        self.conn = self.connect_to_database()
        self.cursor = self.conn.cursor()

        self.login_page_frame = LoginPage(self)
        self.main_page_frame = MainPage(self)

        self.show_login_page()
        self.login_page_frame.set_focus()

        self.raspberry_id = "2"
        self.workstation_id = "2"
        self.device_name = "Raspberry 2"

        self.current_worker_id = None
        self.current_work_order_id = None
        
    def connect_to_database(self):
        try:
            connection = mysql.connector.connect(
                host='10.10.2.15',
                database='paperless',
                user='root',
                password='admin321'
            )
            if connection.is_connected():
                print("Successful connection to the database")
                return connection
        except Error as e:
            print(f"Error while connecting to MariaDB: {e}")
            return None    

    def execute_query(self, query, params=None):
        """
        Executes a query and handles reconnection in case of a timeout.
        """
        try:
            if not self.conn or not self.conn.is_connected():
                print("Reconnecting to the database...")
                self.conn = self.connect_to_database()
                self.cursor = self.conn.cursor()
            
            self.cursor.execute(query, params or ())
            return self.cursor.fetchall()
        except mysql.connector.Error as e:
            print(f"Database error: {e}")
            if e.errno == mysql.connector.errorcode.CR_SERVER_LOST or e.errno == mysql.connector.errorcode.CR_SERVER_GONE_ERROR:
                print("Connection lost. Attempting to reconnect...")
                self.conn = self.connect_to_database()
                self.cursor = self.conn.cursor()
                self.cursor.execute(query, params or ())
                return self.cursor.fetchall()
            else:
                raise

    def show_login_page(self):
        self.main_page_frame.pack_forget()
        self.login_page_frame.pack(expand=True, fill='both')
        self.login_page_frame.logged_in = False
        self.login_page_frame.set_focus()

    def show_main_page(self):
        self.login_page_frame.pack_forget()
        self.main_page_frame.pack(expand=True, fill='both')

        query = "SELECT * FROM RaspberryDevices WHERE device_id=%s AND device_name=%s"
        raspberry_device = self.execute_query(query, (self.workstation_id, self.device_name))
        if raspberry_device:
            worker_id = self.get_worker_id()
            login_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if not self.check_worker_already_logged_in(worker_id):
                insert_query = "INSERT INTO WorkerWorkstation (Worker_id, Workstation_ID, Raspberry_Device, Login_Date) VALUES (%s, %s, %s, %s)"
                self.execute_query(insert_query, (worker_id, self.workstation_id, self.device_name, login_date))
                self.conn.commit()
                self.current_worker_id = worker_id
                self.main_page_frame.update_username()
                self.main_page_frame.entry.focus_set()
        else:
            print("Nem található megfelelő Raspberry eszköz az adatbázisban.")

    def get_worker_id(self):
        rfid = self.login_page_frame.entry.get()
        query = "SELECT id FROM Workers WHERE rfid_tag=%s"
        result = self.execute_query(query, (rfid,))
        worker_id = result[0] if result else None
        if worker_id:
            return worker_id[0]
        else:
            print("Nem található megfelelő munkás azonosító az adatbázisban.")
            return None

    def check_worker_already_logged_in(self, worker_id):
        query = "SELECT * FROM WorkerWorkstation WHERE worker_id=%s AND logout_date IS NULL"
        result = self.execute_query(query, (worker_id,))
        return len(result) > 0

    def show_logout_page(self):
        query = "SELECT * FROM WorkerWorkstation WHERE logout_date IS NULL"
        active_login = self.execute_query(query)
        if active_login:
            self.main_page_frame.pack_forget()
            self.main_page_frame.pack(expand=True, fill='both')
            self.main_page_frame.entry.focus_set()
        else:
            print("Nincs aktív bejelentkezés.")

    def logout(self):
        update_query = "UPDATE WorkerWorkstation SET logout_date=%s WHERE logout_date IS NULL"
        self.execute_query(update_query, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
        self.conn.commit()
        self.show_login_page()
        self.login_page_frame.entry.delete(0, tk.END)

class LoginPage(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.label = ttk.Label(self, text="Login Page", font=("Helvetica", 50))
        self.label.pack(padx=10, pady=20)
        
        self.label2 = ttk.Label(self, text="Please scan your card", font=("Helvetica", 25))
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
        query = "SELECT * FROM Workers WHERE rfid_tag=%s"
        worker = self.master.execute_query(query, (rfid,))
        if worker and not self.logged_in:
            self.logged_in = True
            self.master.show_main_page()

    def set_focus(self):
        self.entry.focus_set()

class MainPage(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.label = ttk.Label(self, text="WO Scanning Page", font=("Helvetica", 50))
        self.label.pack(padx=10, pady=10)

        self.username_label = ttk.Label(self, text="User signed in as: ", font=("Helvetica", 20))
        self.username_label.pack(padx=10, pady=5)

        self.entry = ttk.Entry(self, width=30, font=("Helvetica", 20))
        self.entry.pack(padx=20, pady=20)

        self.text_box = tk.Text(self, width=40, height=8, font=("Helvetica", 30))
        self.text_box.pack(padx=10, pady=5)
        self.text_box.bind("<Return>", self.set_text_size)

        self.logout_button = ttk.Button(self, text="Logout", command=self.master.logout)
        self.logout_button.pack(padx=10, pady=10)
        
        image = Image.open("logo.png")
        image = image.resize((400, 200))
        self.logo_image = ImageTk.PhotoImage(image)

        self.logo = tk.Label(self, image=self.logo_image, background="white")
        self.logo.pack(side=tk.BOTTOM, pady=10)

        self.entry.bind("<KeyRelease>", self.read_qr_code)

        self.main_work_order = None
        self.wo_value = None

    def set_text_size(self, event):
        self.text_box.config(font=("Helvetica", 50))    

    def read_qr_code(self, event):
        if event.keysym == "Return":
            qr_code_text = self.entry.get().strip()
            print(f"Entered text: {qr_code_text}")
            if qr_code_text.lower() == "calibrate":
                self.calibrate_ui()
            elif qr_code_text.lower() == "logout":
                self.master.logout()
            else:
                self.process_qr_code(qr_code_text)

    def calibrate_ui(self):
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()

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

        self.update_idletasks()
        self.master.update_idletasks()

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

        query = "SELECT COUNT(*) FROM WorkOrders WHERE WO=%s AND PN=%s"
        pn_count = self.master.execute_query(query, (self.wo_value, pn_value))[0][0]

        if pn_count == 0:
            messagebox.showerror("Error", "PN value not found in the WorkOrders table.")
            self.text_box.delete(1.0, tk.END)
            self.text_box.insert(tk.END, " ")
            print("PN value not found in the WorkOrders table.")
            return

        query = "SELECT COUNT(*) FROM WorkOrders WHERE MASTER_PN=%s AND HIERARCHY IS NOT NULL AND HIERARCHY != ''"
        master_pn_count = self.master.execute_query(query, (master_pn_value,))[0][0]

        if master_pn_count > 0 or not hierarchy:
            self.start_or_complete_work_order(self.wo_value, pn_value, master_pn_value, hierarchy)
        else:
            messagebox.showerror("Error", "Hierarchy is required for this Master PN.")
            self.text_box.delete(1.0, tk.END)
            self.text_box.insert(tk.END, "Invalid hierarchy for Master PN.")
            print("Invalid hierarchy for Master PN.")

    # A többi metódust is átalakítod az execute_query használatával...


    def start_or_complete_work_order(self, wo_value, pn_value, master_pn_value, hierarchy):
        sub1_value = None
        sub2_value = None

        if hierarchy:
            pn_start = hierarchy.find("PN: ")
            pn_end = hierarchy.find(" SUB1: ")
            if pn_start != -1 and pn_end != -1:
                pn_value = hierarchy[pn_start + 4:pn_end].strip()

            sub1_start = hierarchy.find("SUB1: ")
            sub1_end = hierarchy.find(" SUB2: ")
            if sub1_start != -1:
                sub1_value = hierarchy[sub1_start + 6:sub1_end].strip() if sub1_end != -1 else hierarchy[sub1_start + 6:].strip()

            sub2_start = hierarchy.find("SUB2: ")
            if sub2_start != -1:
                sub2_value = hierarchy[sub2_start + 6:].strip()

            print(f"MODIFIED PN: {pn_value}, WO VALUE: {wo_value}, SUB1 VALUE: {sub1_value}, SUB2 VALUE: {sub2_value}")

            if sub2_value:
                query = "SELECT id, HIERARCHY FROM WorkOrders WHERE PN=%s AND WO=%s AND HIERARCHY LIKE %s"
                result = self.master.execute_query(query, (sub2_value, wo_value, f'%PN: {pn_value} SUB1: {sub1_value} SUB2: {sub2_value}%'))
            elif sub1_value:
                query = "SELECT id, HIERARCHY FROM WorkOrders WHERE PN=%s AND WO=%s AND HIERARCHY LIKE %s"
                result = self.master.execute_query(query, (sub1_value, wo_value, f'%PN: {pn_value} SUB1: {sub1_value}%'))
            else:
                result = []

        else:
            query = "SELECT ID FROM WorkOrders WHERE MASTER_PN=%s AND PN=%s"
            work_order_id = self.master.execute_query(query, (master_pn_value, pn_value))
            if work_order_id:
                work_order_id = work_order_id[0][0]
                if self.is_work_order_active(work_order_id):
                    if self.check_all_sub_levels_completed(work_order_id, master_pn_value, pn_value, hierarchy, wo_value):
                        self.complete_work_order(work_order_id)
                    else:
                        messagebox.showerror("Error", "Not all sub-levels are completed or not present in the workstation work order table.")
                        self.text_box.delete(1.0, tk.END)
                        self.text_box.insert(tk.END, "Not all sub-levels are completed.")
                        print("Not all sub-levels are completed or not present in the workstation work order table.")
                        return False
                else:
                    self.start_work_order(work_order_id, hierarchy)
                    return True

        if result:
            work_order_id, hierarchy_value = result[0]

            if self.is_work_order_active(work_order_id):
                if self.check_all_sub_levels_completed(work_order_id, master_pn_value, pn_value, hierarchy, wo_value):
                    self.complete_work_order(work_order_id, hierarchy)
                else:
                    messagebox.showerror("Error", "Not all sub-levels are completed or not present in the workstation work order table.")
                    self.text_box.delete(1.0, tk.END)
                    self.text_box.insert(tk.END, "Not all sub-levels are completed.")
                    print("Not all sub-levels are completed or not present in the workstation work order table.")
            else:
                self.start_work_order(work_order_id, hierarchy)
                return True

            if hierarchy_value:
                sub2_value = self.extract_value(hierarchy_value, "SUB2: ", "")
                if sub2_value and sub2_value != pn_value:
                    self.complete_sub2_work_order(work_order_id)

    def check_all_sub_levels_completed(self, work_order_id, master_pn_value, pn_value, hierarchy, wo_value):
        if master_pn_value == pn_value:
            query = "SELECT id FROM WorkOrders WHERE MASTER_PN=%s"
            work_order_ids = [row[0] for row in self.master.execute_query(query, (master_pn_value,))]
            print(f"WorkOrder IDs for MASTER_PN {master_pn_value}: {work_order_ids}")

            total_count = len(work_order_ids)
            print(f"Total count for MASTER_PN {master_pn_value}: {total_count}")

            query = "SELECT id FROM WorkstationWorkorder WHERE work_id IN (SELECT id FROM WorkOrders WHERE MASTER_PN=%s) AND status='Completed'"
            completed_work_order_ids = [row[0] for row in self.master.execute_query(query, (master_pn_value,))]
            completed_count = len(completed_work_order_ids)
            print(f"Completed WorkOrder IDs for MASTER_PN {master_pn_value}: {completed_work_order_ids}")
            print(f"Completed count for MASTER_PN {master_pn_value}: {completed_count}")

            query = "SELECT ID FROM WORKORDERS WHERE PN=%s"
            simple_pn_id = self.master.execute_query(query, (pn_value,))
            simple_pn_id = simple_pn_id[0][0] if simple_pn_id else None

            for i in work_order_ids:
                if i == simple_pn_id:
                    completed_count += 1

            return completed_count >= total_count

        # A többi logikát hasonlóan alakítjuk át az execute_query használatával...

    def is_work_order_active(self, work_order_id):
        query = "SELECT status FROM WorkstationWorkorder WHERE work_id=%s AND status='Active'"
        result = self.master.execute_query(query, (work_order_id,))
        return len(result) > 0

    def start_work_order(self, work_order_id, hierarchy):
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = "INSERT INTO WorkstationWorkorder (workstation_id, device_id, worker_id, work_id, start_time, status) VALUES (%s, %s, %s, %s, %s, %s)"
        self.master.execute_query(query, (self.master.workstation_id, self.master.raspberry_id, self.master.current_worker_id, work_order_id, start_time, 'Active'))
        self.master.current_work_order_id = work_order_id

        query = "SELECT WO, QTY, ECN, REV FROM Workorders WHERE ID=%s"
        result = self.master.execute_query(query, (work_order_id,))
        wo_value, qty_value, ecn_value, rev_value = result[0]

        self.text_box.delete(1.0, tk.END)
        self.text_box.insert(tk.END, f"WO {wo_value} started.\nWO data: \n\n{hierarchy}\nECN: {ecn_value}\nQT: {qty_value}\nREV: {rev_value}")
        print(f"WO {work_order_id} started.")

    def complete_work_order(self, work_order_id, hierarchy):
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = "UPDATE WorkstationWorkorder SET status='Completed', end_time=%s WHERE work_id=%s AND status='Active'"
        self.master.execute_query(query, (end_time, work_order_id))
        
        query = "SELECT WO, QTY, ECN, REV FROM Workorders WHERE ID=%s"
        result = self.master.execute_query(query, (work_order_id,))
        wo_value, qty_value, ecn_value, rev_value = result[0]

        self.text_box.delete(1.0, tk.END)
        self.text_box.insert(tk.END, f"WO {wo_value} completed.\nWO data: \n\n{hierarchy}\nECN: {ecn_value}\nQT: {qty_value}\nREV: {rev_value}")
        print(f"WO {work_order_id} completed.")

    def complete_sub2_work_order(self, work_order_id):
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = "UPDATE WorkstationWorkorder SET status='Completed', end_time=%s WHERE work_id=%s AND status='Active'"
        self.master.execute_query(query, (end_time, work_order_id))
        print(f"SUB2 WO {work_order_id} completed.")

    def handle_process_qr(self, qr_code_text):
        data = qr_code_text.split("|")
        process_data = {item.split("-")[0]: item.split("-")[1] for item in data if "-" in item}

        if "PROCESS" in process_data and self.master.current_work_order_id:
            process_id = process_data.get("PROCESS", "")
            query = "UPDATE WorkstationWorkorder SET next_station_id=%s WHERE work_id=%s AND status=%s"
            self.master.execute_query(query, (process_id, self.master.current_work_order_id, "Active"))
            self.text_box.delete(1.0, tk.END)
            self.text_box.insert(tk.END, f"WO has been started in station: {process_data}.")

    def handle_station_qr(self, qr_code_text):
        data = qr_code_text.split("|")
        station_data = {item.split("-")[0]: item.split("-")[1] for item in data if "-" in item}

        if "STATION" in station_data and self.master.current_work_order_id:
            station = station_data.get("STATION", "")
            query = "UPDATE WorkstationWorkorder SET process_id=%s WHERE work_id=%s AND status=%s"
            self.master.execute_query(query, (station, self.master.current_work_order_id, "Active"))
            self.text_box.delete(1.0, tk.END)
            self.text_box.insert(tk.END, f"WO has been sent to new station {station_data}.")

    def update_username(self):
        query = "SELECT name FROM Workers WHERE id=%s"
        result = self.master.execute_query(query, (self.master.current_worker_id,))
        worker_name = result[0][0] if result else "Unknown"
        self.username_label.config(text=f"User signed in as: {worker_name}")


    def set_focus(self):
        self.entry.focus_set()

if __name__=="__main__":
    app = RaspberryApp()
    app.mainloop()
