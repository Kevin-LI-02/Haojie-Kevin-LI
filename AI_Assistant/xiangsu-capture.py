import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from PIL import Image, ImageTk
import cv2
import ast
import csv


class VideoAnnotationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Annotation Tool")

        # Canvas to display video frame
        self.canvas = tk.Canvas(root)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Frame for buttons
        self.button_frame = tk.Frame(root)
        self.button_frame.pack(fill=tk.X)

        # Buttons to control the app
        self.load_button = tk.Button(self.button_frame, text="Load Video", command=self.load_video)
        self.load_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Camera selection dropdown
        self.camera_label = tk.Label(self.button_frame, text="Camera:")
        self.camera_label.pack(side=tk.LEFT, padx=(10, 0))

        self.camera_var = tk.StringVar()
        self.camera_dropdown = ttk.Combobox(self.button_frame, textvariable=self.camera_var,
                                            values=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"], width=5)
        self.camera_dropdown.pack(side=tk.LEFT)
        self.camera_dropdown.set("0")

        self.camera_button = tk.Button(self.button_frame, text="Use Camera", command=self.use_camera)
        self.camera_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.pause_button = tk.Button(self.button_frame, text="Pause", command=self.toggle_pause)
        self.pause_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.clear_button = tk.Button(self.button_frame, text="Clear All Boxes", command=self.clear_boxes)
        self.clear_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.quit_button = tk.Button(self.button_frame, text="Quit", command=root.quit)
        self.quit_button.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # Frame for CSV import
        self.csv_frame = tk.Frame(root)
        self.csv_frame.pack(fill=tk.X)

        self.csv_button = tk.Button(self.csv_frame, text="Import CSV", command=self.import_csv)
        self.csv_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.check_button = tk.Button(self.csv_frame, text="Check Coordinates", command=self.check_coordinates)
        self.check_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.csv_label = tk.Label(self.csv_frame, text="No CSV loaded")
        self.csv_label.pack(side=tk.LEFT, padx=5, pady=5)

        # Frame for coordinate display
        self.coord_frame = tk.Frame(root, height=30, bg="white")
        self.coord_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # Labels for coordinate display
        self.coord_label = tk.Label(self.coord_frame, text="Coordinates: None", bg="white", font=("Arial", 10))
        self.coord_label.pack(side=tk.LEFT, padx=5, pady=5)

        # Copy button
        self.copy_button = tk.Button(self.coord_frame, text="Copy Coordinates", command=self.copy_coordinates)
        self.copy_button.pack(side=tk.RIGHT, padx=5, pady=5)

        # Dwell time or Station name button
        self.switch_button = tk.Button(self.coord_frame, text="Dwell time or Station name",
                                      command=self.switch_coord_order)
        self.switch_button.pack(side=tk.RIGHT, padx=5, pady=5)

        # Hint frame at the very bottom
        self.hint_frame = tk.Frame(root, bg="lightyellow", height=20)
        self.hint_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # Hint label
        self.hint_label = tk.Label(self.hint_frame,
                                   text="Please click this button before copying the coordinates of dwell time and station name.",
                                   bg="lightyellow", font=("Arial", 9), fg="black", justify=tk.CENTER)
        self.hint_label.pack(pady=2)

        # Variables
        self.video = None
        self.current_frame = None
        self.tk_frame = None
        self.is_paused = False
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.rectangles = []  # Store all rectangle IDs
        self.csv_data = {}  # Store CSV coordinate data
        self.csv_rectangles = []  # Store rectangles from CSV
        self.coord_order_normal = True  # True: x0,y0,x1,y1; False: y0,y1,x0,x1

        # Camera resolution settings
        self.camera_width = 1920
        self.camera_height = 1080

        # Bind mouse events
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)

    def load_video(self):
        file_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv")])
        if not file_path:
            return

        # Release any existing video source
        if self.video:
            self.video.release()

        # Load the video
        self.video = cv2.VideoCapture(file_path)
        self.is_paused = False
        self.update_frame()

    def use_camera(self):
        camera_id = int(self.camera_var.get())

        # Release any existing video source
        if self.video:
            self.video.release()

        # Open camera
        self.video = cv2.VideoCapture(camera_id)
        if not self.video.isOpened():
            messagebox.showerror("Error", f"Could not open camera {camera_id}")
            return

        # Set camera resolution to match OBS virtual camera (1920x1080)
        self.video.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
        self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)

        # Check if resolution was set successfully
        actual_width = int(self.video.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.video.get(cv2.CAP_PROP_FRAME_HEIGHT))

        print(f"Requested resolution: {self.camera_width}x{self.camera_height}")
        print(f"Actual resolution: {actual_width}x{actual_height}")

        if actual_width != self.camera_width or actual_height != self.camera_height:
            messagebox.showwarning("Resolution Warning",
                                   f"Camera resolution is {actual_width}x{actual_height}\n"
                                   f"Expected {self.camera_width}x{self.camera_height}\n"
                                   "Coordinates may not be accurate.")

        self.is_paused = False
        self.update_frame()

    def update_frame(self):
        if self.video and not self.is_paused:
            ret, frame = self.video.read()
            if ret:
                self.current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.display_frame()
                # Redraw all rectangles on the new frame
                self.redraw_rectangles()
                self.redraw_csv_rectangles()
                self.root.after(10, self.update_frame)  # Adjust for frame rate
            else:
                self.video.release()
                self.video = None

    def display_frame(self):
        img = Image.fromarray(self.current_frame)
        self.tk_frame = ImageTk.PhotoImage(img)
        self.canvas.config(width=img.width, height=img.height)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_frame)

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        if not self.is_paused and self.video:
            self.update_frame()

    def on_mouse_press(self, event):
        if self.current_frame is not None:
            self.start_x = event.x
            self.start_y = event.y
            self.rect_id = self.canvas.create_rectangle(
                self.start_x, self.start_y, self.start_x, self.start_y,
                outline="red", width=2, tags="rectangle"
            )

    def on_mouse_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)

    def on_mouse_release(self, event):
        if self.current_frame is not None:
            end_x, end_y = event.x, event.y
            # Store the rectangle ID
            self.rectangles.append(self.rect_id)

            # Update coordinate display
            coord_text = f"{self.start_x}, {self.start_y}, {end_x}, {end_y}"
            self.coord_label.config(text=coord_text)

            print(f"Rectangle: Start ({self.start_x}, {self.start_y}), End ({end_x}, {end_y})")
            print(f"Coordinates: {self.start_x}, {self.start_y}, {end_x}, {end_y}")

    def clear_boxes(self):
        """Remove all rectangles from canvas"""
        for rect_id in self.rectangles + self.csv_rectangles:
            self.canvas.delete(rect_id)
        self.rectangles = []
        self.csv_rectangles = []
        self.coord_label.config(text="Coordinates: None")

    def redraw_rectangles(self):
        """Redraw all user-drawn rectangles when the frame updates"""
        for rect_id in self.rectangles:
            coords = self.canvas.coords(rect_id)
            if coords:  # If rectangle exists
                self.canvas.delete(rect_id)
                new_rect_id = self.canvas.create_rectangle(
                    coords[0], coords[1], coords[2], coords[3],
                    outline="red", width=2, tags="rectangle"
                )
                # Update the stored ID
                index = self.rectangles.index(rect_id)
                self.rectangles[index] = new_rect_id

    def redraw_csv_rectangles(self):
        """Redraw all CSV rectangles when the frame updates"""
        for rect_id in self.csv_rectangles:
            coords = self.canvas.coords(rect_id)
            if coords:  # If rectangle exists
                self.canvas.delete(rect_id)
                new_rect_id = self.canvas.create_rectangle(
                    coords[0], coords[1], coords[2], coords[3],
                    outline="blue", width=2, tags="csv_rectangle"
                )
                # Update the stored ID
                index = self.csv_rectangles.index(rect_id)
                self.csv_rectangles[index] = new_rect_id

    def copy_coordinates(self):
        """Copy current coordinates to clipboard"""
        if self.coord_label.cget("text") != "Coordinates: None":
            self.root.clipboard_clear()
            self.root.clipboard_append(self.coord_label.cget("text"))
            self.root.update()  # Now it stays on the clipboard after the window is closed

    def switch_coord_order(self):
        """Switch between coordinate orders"""
        current_text = self.coord_label.cget("text")
        if current_text != "Coordinates: None":
            # Extract coordinates from the label text
            if current_text.startswith("Coordinates: "):
                coords_str = current_text.replace("Coordinates: ", "")
            else:
                coords_str = current_text

            try:
                coords = [int(x.strip()) for x in coords_str.split(',')]
                if len(coords) == 4:
                    if self.coord_order_normal:
                        # Switch to y0,y1,x0,x1
                        new_coords = f"{coords[1]}, {coords[3]}, {coords[0]}, {coords[2]}"
                        self.coord_order_normal = False
                        self.switch_button.config(text="Normal Coordinates")
                    else:
                        # Switch back to x0,y0,x1,y1
                        new_coords = f"{coords[2]}, {coords[0]}, {coords[3]}, {coords[1]}"
                        self.coord_order_normal = True
                        self.switch_button.config(text="Dwell time or Station name")

                    self.coord_label.config(text=new_coords)
            except ValueError:
                messagebox.showerror("Error", "Invalid coordinate format")

    def import_csv(self):
        """Import CSV file with coordinate data"""
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return

        try:
            with open(file_path, 'r') as file:
                reader = csv.DictReader(file)
                self.csv_data = {}
                for row in reader:
                    key = row['key']
                    value = row['value']
                    self.csv_data[key] = value
                    print(f"CSV loaded - Key: {key}, Value: {value}")  # 添加调试输出

            self.csv_label.config(text=f"CSV loaded: {len(self.csv_data)} entries")
            print(f"CSV data loaded: {self.csv_data}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV: {str(e)}")

    def check_coordinates(self):
        """Display coordinates from CSV file on the video"""
        if not self.csv_data:
            messagebox.showwarning("Warning", "No CSV data loaded")
            return

        # Clear existing CSV rectangles
        for rect_id in self.csv_rectangles:
            self.canvas.delete(rect_id)
        self.csv_rectangles = []

        # Parse and display coordinates
        for key, value in self.csv_data.items():
            try:
                if key == "signal_id_position_setting":
                    # Format: "2801,(156, 726, 164, 736);2802,(236, 755, 247, 764);..."
                    items = value.split(';')
                    for item in items:
                        if item and '(' in item and ')' in item:
                            # 处理可能的信号ID和坐标
                            if ',' in item and '(' in item:
                                # 分割信号ID和坐标部分
                                signal_part, coords_part = item.split('(', 1)
                                coords_str = coords_part.rstrip(')')
                                coords = [int(x.strip()) for x in coords_str.split(',')]
                                if len(coords) == 4:
                                    rect_id = self.canvas.create_rectangle(
                                        coords[0], coords[1], coords[2], coords[3],
                                        outline="blue", width=2, tags="csv_rectangle"
                                    )
                                    self.csv_rectangles.append(rect_id)
                                    print(f"Added signal region: {coords}")

                elif key == "regions":
                    # Format: "{1: (1304, 699, 1339, 725), 2: (1306, 812, 1341, 838)}"
                    regions_dict = ast.literal_eval(value)
                    for region_id, coords in regions_dict.items():
                        if len(coords) == 4:
                            rect_id = self.canvas.create_rectangle(
                                coords[0], coords[1], coords[2], coords[3],
                                outline="blue", width=2, tags="csv_rectangle"
                            )
                            self.csv_rectangles.append(rect_id)
                            print(f"Added region {region_id}: {coords}")

                elif key == "dwell_time_regions":
                    # Format: "{1: (512, 528, 1239, 1291), 2: (531, 548, 1239, 1291)}"
                    # Note: Order is (y0, y1, x0, x1) - convert to (x0, y0, x1, y1)
                    regions_dict = ast.literal_eval(value)
                    for region_id, coords in regions_dict.items():
                        if len(coords) == 4:
                            # Convert from (y0, y1, x0, x1) to (x0, y0, x1, y1)
                            x0, y0, x1, y1 = coords[2], coords[0], coords[3], coords[1]
                            rect_id = self.canvas.create_rectangle(
                                x0, y0, x1, y1,
                                outline="blue", width=2, tags="csv_rectangle"
                            )
                            self.csv_rectangles.append(rect_id)
                            print(f"Added dwell time region {region_id}: ({x0}, {y0}, {x1}, {y1})")

                elif key == "station_region":
                    # Format: "(402, 455, 1125, 1514)" - 顺序也是 (y0, y1, x0, x1)
                    # 需要转换为 (x0, y0, x1, y1)
                    coords = ast.literal_eval(value)
                    if len(coords) == 4:
                        # Convert from (y0, y1, x0, x1) to (x0, y0, x1, y1)
                        x0, y0, x1, y1 = coords[2], coords[0], coords[3], coords[1]
                        rect_id = self.canvas.create_rectangle(
                            x0, y0, x1, y1,
                            outline="blue", width=2, tags="csv_rectangle"
                        )
                        self.csv_rectangles.append(rect_id)
                        print(f"Added station region: ({x0}, {y0}, {x1}, {y1})")

            except Exception as e:
                print(f"Error parsing {key}: {str(e)}")

        print(f"Displayed {len(self.csv_rectangles)} rectangles from CSV")


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoAnnotationApp(root)
    root.mainloop()