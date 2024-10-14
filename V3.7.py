import os



if os.environ.get('DISPLAY','') == '':



    print('no display found. Using :0.0')



    os.environ.__setitem__('DISPLAY', ':0.0')



import tkinter as tk



from tkinter import ttk



from tkinter import messagebox



from ttkbootstrap import Style



import mysql.connector



from mysql.connector import connect, Error, errors





from datetime import datetime



from PIL import Image, ImageTk

import socket

import netifaces as ni



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





        self.device_name = socket.gethostname()

        self.raspberry_id = socket.gethostbyname(self.device_name)



        self.workstation_id = "2"

        

        # WiFi interfÃ©sz (wlan0) IP cÃ­mÃ©nek lekÃ©rdezÃ©se

        wifi_interface = 'wlan0'

        try:

            ip_address = ni.ifaddresses(wifi_interface)[ni.AF_INET][0]['addr']

        except KeyError:

            ip_address = 'Nincs WiFi kapcsolat vagy az interfÃ©sz nem elÃ©rhetÅ‘'

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

            connection = connect(

                host='10.10.2.15',

                database='paperless',

                user='root',

                password='admin321',

                connection_timeout=10  # Set a timeout for the connection

            )

            if connection.is_connected():

                print("Successful connection to the database.")

                return connection

        except Error as e:

            print(f"Error while connecting to the database: {e}")

            return None



    def execute_query(self, query, params=None, fetchone=False, caller=None):

        conn = self.connect_to_database()  # Establish the connection before executing the query

        if conn:

            cursor = conn.cursor()

            try:

                # Log the query execution start

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

                conn.commit()

                print(f"Query committed: {query}")

                return result

            

            # Handle specific MySQL and connection-related errors

            except errors.InterfaceError as ie:

                self.log_error_in_db(str(ie), "InterfaceError")

                print(f"InterfaceError: {ie} (query: {query}, called by: {caller})")

            except errors.OperationalError as oe:

                self.log_error_in_db(str(oe), "OperationalError")

                print(f"OperationalError: {oe} (query: {query}, called by: {caller})")

            except errors.DatabaseError as de:

                self.log_error_in_db(str(de), "DatabaseError")

                print(f"DatabaseError: {de} (query: {query}, called by: {caller})")

            except TimeoutError as te:

                self.log_error_in_db(str(te), "TimeoutError")

                print(f"A kapcsolat idÅ‘tÃºllÃ©pÃ©st szenvedett el. (query: {query}, called by: {caller})")

            except errors.ProgrammingError as pe:

                self.log_error_in_db(str(pe), "ProgrammingError")

                print(f"ProgrammingError: {pe} (query: {query}, called by: {caller})")

            except Exception as e:

                self.log_error_in_db(str(e), "GeneralError")

                print(f"MÃ¡s hiba tÃ¶rtÃ©nt: {e} (query: {query}, called by: {caller})")

            

            finally:

                # Clean up and close the cursor and connection

                try:

                    if cursor.with_rows and not fetchone:  # Only fetch remaining rows if needed

                        remaining_results = cursor.fetchall()

                        print(f"Remaining results consumed: {remaining_results}")

                except errors.Error as consume_error:

                    print(f"Error consuming remaining results: {consume_error} for query: {query}")

                

                # Attempt to close the cursor

                try:

                    cursor.close()

                    print(f"Cursor closed for query: {query}")

                except errors.Error as close_cursor_error:

                    print(f"Error closing cursor: {close_cursor_error} for query: {query}")

                

                # Attempt to close the connection

                try:

                    conn.close()

                    print("Connection closed.")

                except errors.Error as close_conn_error:

                    print(f"Error closing connection: {close_conn_error}")



        return None





    

    def log_error_in_db(self, error_message, error_type):

        try:

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            

            # Insert the error details into the Errors table

            self.master.execute_query(

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

        result = self.execute_query(

            "SELECT * FROM RaspberryDevices WHERE device_id=%s AND device_name=%s",

            (self.raspberry_id, self.device_name),

            fetchone=True,

            caller="show_main_page"

        )

        if result:

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

        result = self.execute_query(

            "SELECT id FROM Workers WHERE rfid_tag=%s", (rfid,),

            fetchone=True,

            caller="get_worker_id"

        )

        if result:

            return result[0]

        else:

            print("Nem talÃ¡lhatÃ³ megfelelÅ‘ munkÃ¡s azonosÃ­tÃ³ az adatbÃ¡zisban.")

            return None



    def check_worker_already_logged_in(self, worker_id):

        result = self.execute_query(

            "SELECT * FROM WorkerWorkstation WHERE worker_id=%s AND logout_date IS NULL",

            (worker_id,),

            fetchone=True,

            caller="check_worker_already_logged_in"

        )

        return result is not None



    def logout(self):

        self.execute_query(

            "UPDATE WorkerWorkstation SET logout_date=%s WHERE logout_date IS NULL",

            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),),

            caller="logout"

        )

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

            '+': '1', 'ľ': '2', 'š': '3', 'č': '4', 'ť': '5',

            'ž': '6', 'ý': '7', 'á': '8', 'í­': '9', 'é': '0',

            '=': '-', '%': '=', 'Q': 'q', 'W': 'w', 'E': 'e',

            'R': 'r', 'T': 't', 'Z': 'z', 'U': 'u', 'I': 'i',

            'O': 'o', 'P': 'p', 'Ãº': '[', 'Ã¤': ']', '': '\\',

            'A': 'a', 'S': 's', 'D': 'd', 'F': 'f', 'G': 'g',

            'H': 'h', 'J': 'j', 'K': 'k', 'L': 'l', 'Ã´': ';',

            'Â§': "'", 'Y': 'y', 'X': 'x', 'C': 'c', 'V': 'v',

            'B': 'b', 'N': 'n', 'M': 'm', '?': ',', ':': '.',

            '_': '/', '?': '`', '!': '1', '"': '2', 'Â§': '3',

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

        result = self.master.execute_query(

            "SELECT * FROM Workers WHERE rfid_tag=%s", (rfid,),

            fetchone=True,

            caller="search_worker"

        )

        if result and not self.logged_in:

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

        # Parse the QR code text into key-value pairs

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



        # Check if PN exists for the given WO

        pn_count = self.master.execute_query(

            "SELECT COUNT(*) FROM WorkOrders WHERE WO=%s AND PN=%s",

            (self.wo_value, pn_value),

            fetchone=True,

            caller="handle_work_order_qr"

        )[0]



        if pn_count == 0:

            messagebox.showerror("Error", "PN value not found in the WorkOrders table.")

            self.text_box.delete(1.0, tk.END)

            self.text_box.insert(tk.END, " ")

            print("PN value not found in the WorkOrders table.")

            return



        # Check if hierarchy exists for the given MASTER_PN

        master_pn_count = self.master.execute_query(

            "SELECT COUNT(*) FROM WorkOrders WHERE MASTER_PN=%s AND HIERARCHY IS NOT NULL AND HIERARCHY != ''",

            (master_pn_value,),

            fetchone=True,

            caller="handle_work_order_qr"

        )[0]



        if master_pn_count > 0 or not hierarchy:

            self.start_or_complete_work_order(self.wo_value, pn_value, master_pn_value, hierarchy)

        else:

            messagebox.showerror("Error", "Hierarchy is required for this Master PN.")

            self.text_box.delete(1.0, tk.END)

            self.text_box.insert(tk.END, "Invalid hierarchy for Master PN.")

            print("Invalid hierarchy for Master PN.")









    def start_or_complete_work_order(self, wo_value, pn_value, master_pn_value, hierarchy):

        sub1_value = None

        sub2_value = None



        # Extract values from hierarchy if provided

        if hierarchy:

            # FIND PN

            pn_value = self.extract_value(hierarchy, "PN: ", " SUB1")

            # FIND SUB1

            sub1_value = self.extract_value(hierarchy, "SUB1: ", " SUB2")

            # FIND SUB2

            sub2_value = self.extract_value(hierarchy, "SUB2: ", "")



            print(f"MODIFIED PN: {pn_value}, WO VALUE: {wo_value}, SUB1 VALUE: {sub1_value}, SUB2 VALUE: {sub2_value}")



            # Query based on the extracted values

            if sub2_value:

                result = self.master.execute_query(

                    "SELECT id, HIERARCHY FROM WorkOrders WHERE PN=%s AND WO=%s AND HIERARCHY LIKE %s",

                    (sub2_value, wo_value, f'%PN: {pn_value} SUB1: {sub1_value} SUB2: {sub2_value}%'),

                    fetchone=True,

                    caller="start_or_complete_work_order"

                )

            elif sub1_value:

                result = self.master.execute_query(

                    "SELECT id, HIERARCHY FROM WorkOrders WHERE PN=%s AND WO=%s AND HIERARCHY LIKE %s",

                    (sub1_value, wo_value, f'%PN: {pn_value} SUB1: {sub1_value}%'),

                    fetchone=True,

                    caller="start_or_complete_work_order"

                )

            else:

                result = None

        else:

            # Query when no hierarchy is provided

            result = self.master.execute_query(

                "SELECT ID FROM WorkOrders WHERE MASTER_PN=%s AND PN=%s",

                (master_pn_value, pn_value),

                fetchone=True,

                caller="start_or_complete_work_order"

            )



            if result:

                work_order_id = result[0]



                # Check if the work order is active and complete it if necessary

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



        # Handle result if hierarchy search was successful

        if result:

            work_order_id, hierarchy_value = result



            # Check if the work order is active and complete it if necessary

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



            # Only attempt to complete sub2 work orders separately

            if hierarchy_value:

                sub2_value = self.extract_value(hierarchy_value, "SUB2: ", "")

                if sub2_value and sub2_value != pn_value:  # Ensure sub2_value is not the same as pn_value

                    self.complete_sub2_work_order(work_order_id)









    def check_all_sub_levels_completed(self, work_order_id, master_pn_value, pn_value, hierarchy, wo_value):

        # Case 1: When MASTER_PN and PN are the same

        if master_pn_value == pn_value:

            # Get all work order IDs associated with the MASTER_PN

            work_order_ids = [row[0] for row in self.master.execute_query(

                "SELECT id FROM WorkOrders WHERE MASTER_PN=%s",

                (master_pn_value,),

                caller="check_all_sub_levels_completed"

            )]

            print(f"WorkOrder IDs for MASTER_PN {master_pn_value}: {work_order_ids}")



            total_count = len(work_order_ids)

            print(f"Total count for MASTER_PN {master_pn_value}: {total_count}")



            # Get the completed work orders associated with MASTER_PN

            completed_work_order_ids = [row[0] for row in self.master.execute_query(

                "SELECT id FROM WorkstationWorkorder WHERE work_id IN (SELECT id FROM WorkOrders WHERE MASTER_PN=%s) AND status='Completed'",

                (master_pn_value,),

                caller="check_all_sub_levels_completed"

            )]

            completed_count = len(completed_work_order_ids)

            print(f"Completed WorkOrder IDs for MASTER_PN {master_pn_value}: {completed_work_order_ids}")

            print(f"Completed count for MASTER_PN {master_pn_value}: {completed_count}")



            # Get the simple PN ID

            simple_pn_id = self.master.execute_query(

                "SELECT ID FROM WorkOrders WHERE PN=%s", (pn_value,),

                fetchone=True, caller="check_all_sub_levels_completed"

            )

            if simple_pn_id:

                for i in work_order_ids:

                    if i == simple_pn_id[0]:

                        print(f"i: {i}, workorder_ids: {simple_pn_id[0]}")

                        completed_count += 1

                        print("total_count", completed_count)



            return completed_count >= total_count



        # Case 2: When hierarchy is an empty string

        else:

            if hierarchy == "":

                first_level_workid_list = []

                first_level_completed_count = 0



                print(f"\nMaster PN: {master_pn_value}, PN: {pn_value}")



                # Get the first-level sub work orders based on hierarchy

                first_level_sub = self.master.execute_query(

                    "SELECT HIERARCHY FROM WorkOrders WHERE MASTER_PN=%s", (master_pn_value,),

                    caller="check_all_sub_levels_completed"

                )



                for i in first_level_sub:

                    hierarchy_value = i[0]



                    # Extract the first-level PN and SUB1 values

                    first_level_pn_value = self.extract_value(hierarchy_value, "PN: ", " SUB1")

                    first_level_sub1_value = self.extract_value(hierarchy_value, "SUB1: ", " SUB2")



                    if first_level_pn_value == pn_value:

                        print(f"\n\nfirst level pn: {first_level_pn_value}\nPN: {pn_value}\nSUB1: {first_level_sub1_value}")



                        first_level_workid = self.master.execute_query(

                            "SELECT ID FROM WorkOrders WHERE HIERARCHY LIKE %s",

                            (f'%PN: {first_level_pn_value} SUB1: {first_level_sub1_value}%',),

                            fetchone=True,

                            caller="check_all_sub_levels_completed"

                        )



                        if first_level_workid:

                            first_level_workid_list.append(first_level_workid[0])



                # Remove duplicate work IDs

                unique_workid_list = list(set(first_level_workid_list))

                first_level_total_count = len(unique_workid_list)

                print(f"Total count: {first_level_total_count}")



                # Check the status of each work order ID

                for workid in unique_workid_list:

                    print(f"unique_workid_list: {unique_workid_list}")

                    status = self.master.execute_query(

                        "SELECT STATUS FROM WorkstationWorkorder WHERE work_id=%s", (workid,),

                        fetchone=True,

                        caller="check_all_sub_levels_completed"

                    )



                    if status and status[0] == 'Completed':

                        first_level_completed_count += 1

                        print(f"\nCompleted Count: {first_level_completed_count}")



                # Return true if all work orders are completed

                if first_level_completed_count == first_level_total_count and first_level_total_count > 0:

                    return True



            # Extract PN, SUB1, and SUB2 from the hierarchy for further checks

            sub1_value = self.extract_value(hierarchy, "SUB1: ", " SUB2")

            sub2_value = self.extract_value(hierarchy, "SUB2: ", "")



            work_orders = self.master.execute_query(

                "SELECT * FROM WorkOrders WHERE MASTER_PN=%s", (master_pn_value,),

                caller="check_all_sub_levels_completed"

            )



            # Process work orders for further sub-level completion checks

            for work_order in work_orders:

                current_hierarchy = work_order[16]  # Assuming HIERARCHY is in the 16th column

                if current_hierarchy:

                    current_pn = self.extract_value(current_hierarchy, "PN: ", " SUB1")

                    current_sub1 = self.extract_value(current_hierarchy, "SUB1: ", " SUB2")

                    current_sub2 = self.extract_value(current_hierarchy, "SUB2: ", "")



                    if current_pn == pn_value and current_sub1 == sub1_value:

                        if current_pn == pn_value and current_sub2 == sub2_value:

                            return True



                        # Check for sub-level completion in the workstation work orders

                        completed_sub2_count = self.master.execute_query(

                            "SELECT COUNT(*) FROM WorkstationWorkorder WHERE work_id IN "

                            "(SELECT id FROM WorkOrders WHERE PN=%s AND MASTER_PN=%s AND HIERARCHY LIKE %s AND status='Completed')",

                            (current_sub2, master_pn_value, f'%PN: {pn_value} SUB1: {sub1_value} SUB2: {current_sub2}%'),

                            fetchone=True,

                            caller="check_all_sub_levels_completed"

                        )[0]



                        total_sub2_count = self.master.execute_query(

                            "SELECT COUNT(*) FROM WorkstationWorkorder WHERE work_id IN "

                            "(SELECT id FROM WorkOrders WHERE PN=%s AND MASTER_PN=%s AND HIERARCHY LIKE %s)",

                            (current_sub2, master_pn_value, f'%PN: {pn_value} SUB1: {sub1_value} SUB2: {current_sub2}%'),

                            fetchone=True,

                            caller="check_all_sub_levels_completed"

                        )[0]



                        print(f"Completed count for SUB2 {current_sub2}: {completed_sub2_count}")

                        print(f"Total count for SUB2 {current_sub2}: {total_sub2_count}")



                        if completed_sub2_count == total_sub2_count and total_sub2_count > 0:

                            return True



        return False









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

        # Check if the work order is active

        result = self.master.execute_query(

            "SELECT status FROM WorkstationWorkorder WHERE work_id=%s AND status='Active'", 

            (work_order_id,),

            fetchone=True,

            caller="is_work_order_active"

        )

        return result is not None





    def start_work_order(self, work_order_id, hierarchy):

        # Start the work order and insert relevant details

        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")



        self.master.execute_query(

            "INSERT INTO WorkstationWorkorder (workstation_id, device_id, worker_id, work_id, start_time, status) "

            "VALUES (%s, %s, %s, %s, %s, %s)",

            (self.master.workstation_id, self.master.raspberry_id, self.master.current_worker_id, 

             work_order_id, start_time, 'Active'),

            caller="start_work_order"

        )



        # Set the current work order ID

        self.master.current_work_order_id = work_order_id



        # Fetch work order details

        result = self.master.execute_query(

            "SELECT WO, QTY, ECN, REV FROM Workorders WHERE ID=%s", 

            (work_order_id,),

            fetchone=True,

            caller="start_work_order"

        )



        if result:

            wo_value, qty_value, ecn_value, rev_value = result

            self.master.conn.commit()



            self.text_box.delete(1.0, tk.END)

            self.text_box.insert(tk.END, f"WO {wo_value} started.\nWO data: \n\n{hierarchy}\nECN: {ecn_value}\nQT: {qty_value}\nREV: {rev_value}")

            print(f"WO {work_order_id} started.")





    def complete_work_order(self, work_order_id, hierarchy):

        # Complete the work order

        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")



        self.master.execute_query(

            "UPDATE WorkstationWorkorder SET status='Completed', end_time=%s WHERE work_id=%s AND status='Active'", 

            (end_time, work_order_id),

            caller="complete_work_order"

        )



        # Fetch work order details

        result = self.master.execute_query(

            "SELECT WO, QTY, ECN, REV FROM Workorders WHERE ID=%s", 

            (work_order_id,),

            fetchone=True,

            caller="complete_work_order"

        )



        if result:

            wo_value, qty_value, ecn_value, rev_value = result

            self.master.conn.commit()



            self.text_box.delete(1.0, tk.END)

            self.text_box.insert(tk.END, f"WO {wo_value} completed.\nWO data: \n\n{hierarchy}\nECN: {ecn_value}\nQT: {qty_value}\nREV: {rev_value}")

            print(f"WO {work_order_id} completed.")





    def complete_sub2_work_order(self, work_order_id):

        # Complete the SUB2 work order

        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")



        self.master.execute_query(

            "UPDATE WorkstationWorkorder SET status='Completed', end_time=%s WHERE work_id=%s AND status='Active'", 

            (end_time, work_order_id),

            caller="complete_sub2_work_order"

        )



        print(f"SUB2 WO {work_order_id} completed.")





    def handle_process_qr(self, qr_code_text):

        # Handle PROCESS QR codes

        data = qr_code_text.split("|")

        process_data = {item.split("-")[0]: item.split("-")[1] for item in data if "-" in item}



        if "PROCESS" in process_data and self.master.current_work_order_id:

            process_id = process_data.get("PROCESS", "")

            self.master.execute_query(

                "UPDATE WorkstationWorkorder SET next_station_id=%s WHERE work_id=%s AND status=%s", 

                (process_id, self.master.current_work_order_id, "Active"),

                caller="handle_process_qr"

            )

            self.master.conn.commit()



            self.text_box.delete(1.0, tk.END)

            self.text_box.insert(tk.END, f"WO has been started in station: {process_data}.")





    def handle_station_qr(self, qr_code_text):

        # Handle STATION QR codes

        data = qr_code_text.split("|")

        station_data = {item.split("-")[0]: item.split("-")[1] for item in data if "-" in item}



        if "STATION" in station_data and self.master.current_work_order_id:

            station = station_data.get("STATION", "")

            self.master.execute_query(

                "UPDATE WorkstationWorkorder SET process_id=%s WHERE work_id=%s AND status=%s", 

                (station, self.master.current_work_order_id, "Active"),

                caller="handle_station_qr"

            )

            self.master.conn.commit()



            self.text_box.delete(1.0, tk.END)

            self.text_box.insert(tk.END, f"WO has been sent to new station {station_data}.")





    def update_username(self):

        # Update the username label based on the worker ID

        worker_id = self.master.current_worker_id

        result = self.master.execute_query(

            "SELECT name FROM Workers WHERE id=%s", 

            (worker_id,),

            fetchone=True,

            caller="update_username"

        )



        if result:

            self.username_label.config(text=f"User signed in as: {result[0]}")







    def set_focus(self):



        self.entry.focus_set()







if __name__=="__main__":



    app = RaspberryApp()



    app.mainloop()



