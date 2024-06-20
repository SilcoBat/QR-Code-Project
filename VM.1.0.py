import tkinter as tk
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from tkinter import messagebox

class RaspberryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Raspberry App")
        self.geometry("600x400")

        # Database connection
        self.conn = self.connect_to_database()
        self.cursor = self.conn.cursor()

        # Initialize LoginPage and MainPage frames
        self.login_page_frame = LoginPage(self)
        self.main_page_frame = MainPage(self)

        # Initially show the LoginPage frame
        self.show_login_page()

        # Set cursor to entry field on the appropriate frame
        self.login_page_frame.set_focus()

        self.raspberry_id = "2"
        self.workstation_id = "2"
        self.device_name = "Raspberry 2"

        self.current_worker_id = None
        self.current_work_order_id = None

    def connect_to_database(self):
        try:
            connection = mysql.connector.connect(
                host='10.10.2.15',     # Az adatbázis hosztja (pl. 'localhost' vagy '127.0.0.1')
                database='paperless',  # Az adatbázis neve
                user='root',  # Az adatbázis felhasználói neve
                password='admin321'  # Az adatbázis jelszava
            )
            if connection.is_connected():
                print("Successful connection to the database")
                return connection
        except Error as e:
            print(f"Error while connecting to MariaDB: {e}")
            return None

    def show_login_page(self):
        self.main_page_frame.pack_forget()
        self.login_page_frame.pack()
        self.login_page_frame.logged_in = False
        self.login_page_frame.set_focus()

    def show_main_page(self):
        self.login_page_frame.pack_forget()
        self.main_page_frame.pack()

        self.cursor.execute("SELECT * FROM RaspberryDevices WHERE device_id=%s AND device_name=%s", (self.workstation_id, self.device_name))
        raspberry_device = self.cursor.fetchone()

        if raspberry_device:
            worker_id = self.get_worker_id()
            login_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if not self.check_worker_already_logged_in(worker_id):
                self.cursor.execute("INSERT INTO WorkerWorkstation (Worker_id, Workstation_ID, Raspberry_Device, Login_Date) VALUES (%s, %s, %s, %s)",
                                    (worker_id, self.workstation_id, self.device_name, login_date))
                self.conn.commit()
                print(self.cursor.fetchall())
                self.current_worker_id = worker_id
                self.main_page_frame.update_username()
                self.main_page_frame.entry.focus_set()
        else:
            print("Nem található megfelelő Raspberry eszköz az adatbázisban.")


    def get_worker_id(self):
        rfid = self.login_page_frame.entry.get()
        self.cursor.execute("SELECT id FROM Workers WHERE rfid_tag=%s", (rfid,))
        worker_id = self.cursor.fetchone()
        print("Worker ID: ",worker_id)
        if worker_id:
            return worker_id[0]
        else:
            print("Nem található megfelelő munkás azonosító az adatbázisban.")
            return None

    def check_worker_already_logged_in(self, worker_id):
        self.cursor.execute("SELECT * FROM WorkerWorkstation WHERE worker_id=%s AND logout_date IS NULL", (worker_id,))
        existing_record = self.cursor.fetchone()
        return existing_record is not None

    def show_logout_page(self):
        self.cursor.execute("SELECT * FROM WorkerWorkstation WHERE logout_date IS NULL")
        active_login = self.cursor.fetchone()

        if active_login:
            self.main_page_frame.pack_forget()
            self.main_page_frame.pack()
            self.main_page_frame.entry.focus_set()
        else:
            print("Nincs aktív bejelentkezés.")

    def logout(self):
        self.cursor.execute("UPDATE WorkerWorkstation SET logout_date=%s WHERE logout_date IS NULL",
                            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
        self.conn.commit()
        self.show_login_page()
        self.login_page_frame.entry.delete(0, tk.END)

class LoginPage(tk.Frame):
    def __init__(self, master):
        super().__init__(master)

        self.label = tk.Label(self, text="Login Page", font=("Helvetica", 20))
        self.label.pack(padx=10, pady=10)

        self.entry = tk.Entry(self, width=50, font=("Helvetica", 12))
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
        rfid = self.entry.get()  # Az RFID beolvasott értéke
        rfid = rfid.strip()      # Törlés a szóköz karaktereiről, hogy a paraméter ne támogassa
        self.master.cursor.execute("SELECT * FROM Workers WHERE rfid_tag=%s", (rfid,))
        worker = self.master.cursor.fetchone()

        if worker and not self.logged_in:
            self.logged_in = True
            self.master.show_main_page()

    def set_focus(self):
        self.entry.focus_set()

class MainPage(tk.Frame):
    def __init__(self, master):
        super().__init__(master)

        self.label = tk.Label(self, text="Main Page", font=("Helvetica", 20))
        self.label.pack(padx=10, pady=10)

        self.username_label = tk.Label(self, text="User signed in as: ", font=("Helvetica", 12))
        self.username_label.pack(padx=10, pady=5)

        self.entry = tk.Entry(self, width=30, font=("Helvetica", 12), show="•")
        self.entry.pack(padx=10, pady=5)

        self.text_box = tk.Text(self, width=60, height=10)
        self.text_box.pack(padx=10, pady=5)

        self.logout_button = tk.Button(self, text="Logout", command=self.master.logout)
        self.logout_button.pack(pady=20)

        self.entry.bind("<KeyRelease>", self.read_qr_code)

        self.main_work_order = None

    def read_qr_code(self, event):
        if event.keysym == "Return":
            qr_code_text = self.entry.get()
            self.process_qr_code(qr_code_text)

    def process_qr_code(self, qr_code_text):
        if qr_code_text.startswith("WO"):
            self.handle_work_order_qr(qr_code_text)
        elif qr_code_text.startswith("PROCESS"):
            self.handle_process_qr(qr_code_text)
        elif qr_code_text.startswith("STATION"):
            self.handle_station_qr(qr_code_text)
        else:
            self.text_box.delete(1.0, tk.END)
            self.text_box.insert(tk.END, "Invalid QR code.--- Vedd ki nemtom mi baja ---")
        self.entry.delete(0, tk.END)
        self.entry.focus_set()

    def handle_work_order_qr(self, qr_code_text):
        data = qr_code_text.split("|")
        wo_data = {item.split("-")[0]: item.split("-")[1] for item in data if "-" in item}

        wo_value = wo_data.get("WO", "")
        mlt_status = wo_data.get("MLT_STATUS", "")

        if mlt_status.startswith("M"):
            self.master.cursor.execute("SELECT COUNT(*) FROM WorkOrders WHERE WO=%s AND MLT_STATUS LIKE 'S%'", (wo_value,))
            sub_count = self.master.cursor.fetchone()[0]

            self.master.cursor.execute("SELECT COUNT(*) FROM WorkstationWorkorder WHERE work_id IN (SELECT id FROM WorkOrders WHERE WO=%s AND MLT_STATUS LIKE 'S%') AND status!='Completed'", (wo_value,))
            incomplete_sub_count = self.master.cursor.fetchone()[0]

            if sub_count > 0:
                if incomplete_sub_count > 0:
                    messagebox.showerror("Error", f"Main project has {sub_count} sub-projects, but {incomplete_sub_count} are not yet completed or started.")
                    self.text_box.delete(1.0, tk.END)
                    self.text_box.insert(tk.END, " ")
                    return
                else:
                    self.main_work_order = wo_value
                    print(f"Main project with {sub_count} sub-projects.")

        elif mlt_status.startswith("S"):
            self.master.cursor.execute("""
                SELECT COUNT(*)
                FROM WorkstationWorkorder wwo
                JOIN WorkOrders wo ON wwo.work_id = wo.id
                WHERE wo.WO = %s AND wo.MLT_STATUS LIKE 'M%' AND wwo.status = 'Active'
            """, (wo_value,))
            active_main_count = self.master.cursor.fetchone()[0]

            if active_main_count == 0:
                messagebox.showerror("Error", "Main WO is not active.")
                self.text_box.delete(1.0, tk.END)
                self.text_box.insert(tk.END, " ")
                return

        self.master.cursor.execute("SELECT id FROM WorkOrders WHERE WO=%s AND PN=%s", (wo_data.get("WO", ""), wo_data.get("PN", "")))
        work_order_id = self.master.cursor.fetchone()

        if work_order_id:
            worker_id = self.master.current_worker_id
            self.master.cursor.execute("SELECT id, start_time, status FROM WorkstationWorkorder WHERE worker_id=%s AND work_id=%s AND status=%s", (worker_id, work_order_id[0], "Active"))
            existing_work_order = self.master.cursor.fetchone()

            if existing_work_order:
                qty_completed = wo_data.get("QTY", "")
                if qty_completed:
                    confirm = messagebox.askyesno("QTY Check", f"Has the quantity {qty_completed} been completed?")
                    if confirm:
                        self.complete_existing_work_order(existing_work_order, work_order_id, worker_id)
                    else:
                        self.text_box.delete(1.0, tk.END)
                        self.text_box.insert(tk.END, "Quantity not completed. Cannot proceed.")
                        self.entry.delete(0, tk.END)
                        self.entry.focus_set()
                else:
                    self.text_box.delete(1.0, tk.END)
                    self.text_box.insert(tk.END, "QTY not found in the QR code.")
            else:
                self.start_new_work_order(worker_id, work_order_id, wo_data)
        else:
            self.text_box.delete(1.0, tk.END)
            self.text_box.insert(tk.END, "Work order not found in the database.")

    def complete_existing_work_order(self, existing_work_order, work_order_id, worker_id):
        # Ellenőrizni kell, hogy a fő WO befejezhető-e
        self.master.cursor.execute("""
            SELECT WO
            FROM WorkOrders 
            WHERE id=%s AND MLT_STATUS LIKE 'M%'
        """, (work_order_id[0],))
        main_wo = self.master.cursor.fetchone()

        if main_wo:
            main_wo_value = main_wo[0]
            # Ellenőrizni, hogy a fő WO összes sub WO-ja Completed státuszban van-e
            self.master.cursor.execute("""
                SELECT COUNT(*)
                FROM WorkOrders 
                WHERE WO = %s AND MLT_STATUS LIKE 'S%'
            """, (main_wo_value,))
            total_sub_count = self.master.cursor.fetchone()[0]

            self.master.cursor.execute("""
                SELECT COUNT(*)
                FROM WorkOrders wo
                JOIN WorkstationWorkorder wwo ON wo.id = wwo.work_id
                WHERE wo.WO = %s AND wo.MLT_STATUS LIKE 'S%' AND wwo.status = 'Completed'
            """, (main_wo_value,))
            completed_sub_count = self.master.cursor.fetchone()[0]

            if total_sub_count != completed_sub_count:
                messagebox.showerror("Error", f"Cannot complete main WO as there are incomplete sub WOs.")
                return

        self.master.cursor.execute("UPDATE WorkstationWorkorder SET status=%s, end_time=%s WHERE id=%s", ("Completed", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), existing_work_order[0]))
        self.master.conn.commit()
        self.text_box.delete(1.0, tk.END)
        self.text_box.insert(tk.END, "Work order completed.")

    def start_new_work_order(self, worker_id, work_order_id, wo_data):
        # Ellenőrizni, hogy van-e aktív fő WO
        self.master.cursor.execute("""
            SELECT WO 
            FROM WorkOrders 
            WHERE id=%s AND MLT_STATUS LIKE 'M%'
        """, (work_order_id[0],))
        main_wo = self.master.cursor.fetchone()

        if main_wo:
            main_wo_value = main_wo[0]
            # Ellenőrizni, hogy a fő WO elindítható-e
            self.master.cursor.execute("""
                SELECT COUNT(*) 
                FROM WorkOrders wo 
                JOIN WorkstationWorkorder wwo ON wo.id = wwo.work_id 
                WHERE wo.WO = %s AND wo.MLT_STATUS LIKE 'S%' AND wwo.status != 'Completed'
            """, (main_wo_value,))
            incomplete_sub_count = self.master.cursor.fetchone()[0]

            if incomplete_sub_count > 0:
                messagebox.showerror("Error", f"Cannot start main WO as there are {incomplete_sub_count} incomplete sub WOs.")
                return

        self.master.cursor.execute("INSERT INTO WorkstationWorkorder (worker_id, work_id, device_id, workstation_id, status, start_time) VALUES (%s, %s, %s, %s, %s, %s)",
                                   (worker_id, work_order_id[0], self.master.raspberry_id, self.master.workstation_id, "Active", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.master.conn.commit()
        self.master.current_work_order_id = work_order_id[0]
        self.text_box.delete(1.0, tk.END)
        self.text_box.insert(tk.END, "Work order started.")


    def handle_process_qr(self, qr_code_text):
        data = qr_code_text.split("|")
        process_data = {item.split("-")[0]: item.split("-")[1] for item in data if "-" in item}

        if "PROCESS" in process_data and self.master.current_work_order_id:
            process_id = process_data.get("PROCESS", "")
            self.master.cursor.execute("UPDATE WorkstationWorkorder SET next_station_id=%s WHERE work_id=%s AND status=%s", (process_id, self.master.current_work_order_id, "Active"))
            self.master.conn.commit()
            self.text_box.delete(1.0, tk.END)
            self.text_box.insert(tk.END, "Process updated for the current work order.")

    def handle_station_qr(self, qr_code_text):
        data = qr_code_text.split("|")
        station_data = {item.split("-")[0]: item.split("-")[1] for item in data if "-" in item}

        if "STATION" in station_data and self.master.current_work_order_id:
            station = station_data.get("STATION", "")
            self.master.cursor.execute("UPDATE WorkstationWorkorder SET process_id=%s WHERE work_id=%s AND status=%s", (station, self.master.current_work_order_id, "Active"))
            self.master.conn.commit()
            self.text_box.delete(1.0, tk.END)
            self.text_box.insert(tk.END, "Station updated for the current work order.")

    def update_username(self):
        worker_id = self.master.current_worker_id
        self.master.cursor.execute("SELECT name FROM Workers WHERE id=%s", (worker_id,))
        worker = self.master.cursor.fetchone()
        print("Worker: ", worker)
        if worker:
            self.username_label.config(text=f"User signed in as: {worker[0]}")

    def set_focus(self):
        self.entry.focus_set()


if __name__ == "__main__":
    app = RaspberryApp()
    app.mainloop()
