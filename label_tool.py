from pathlib import Path
import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

OUTPUT_DIR = 'output'
DEFAULT_IMAGE = 'tex_note_common_all_v2.png'


def clamp_even(value):
    value = int(value)
    if value < 2:
        return 2
    return value if value % 2 == 0 else value + 1


class GridLabelerApp:
    def __init__(self, root, init_width=1000, init_height=700):
        self.root = root
        self.root.title('2の倍数グリッド選択ラベルツール')
        self.root.geometry(f'{init_width}x{init_height}')
        self.root.minsize(640, 480)

        self.image_path = None
        self.base_image = None
        self.tk_image = None
        self.scale_factor = 1.0
        self.display_width = 0
        self.display_height = 0
        self.resize_job = None
        self.grid_step = 64
        self.start_x = None
        self.start_y = None
        self.current_rect_id = None
        self.current_selection = None
        self.hover_id = None
        self.active_selection_index = None
        self.selections = []

        self.setup_ui()
        self.load_default_image()

    def setup_ui(self):
        self.canvas = tk.Canvas(self.root, bg='black', cursor='cross')
        self.canvas.grid(row=0, column=0, rowspan=6, sticky='nsew')

        control_frame = tk.Frame(self.root, padx=8, pady=8)
        control_frame.grid(row=0, column=1, sticky='nw')

        tk.Label(control_frame, text='画像').grid(row=0, column=0, sticky='w')
        self.image_label = tk.Label(control_frame, text='なし', wraplength=220, justify='left')
        self.image_label.grid(row=0, column=1, sticky='w')

        tk.Button(control_frame, text='画像を開く', command=self.open_image).grid(row=1, column=0, columnspan=2, pady=(4, 8), sticky='ew')

        tk.Label(control_frame, text='グリッド幅 (2の倍数)').grid(row=2, column=0, sticky='w')
        self.grid_step_var = tk.StringVar(value=str(self.grid_step))
        self.grid_step_entry = tk.Entry(control_frame, textvariable=self.grid_step_var, width=6)
        self.grid_step_entry.grid(row=2, column=1, sticky='w')
        tk.Button(control_frame, text='更新', command=self.update_grid_step).grid(row=3, column=0, columnspan=2, pady=(4, 8), sticky='ew')

        tk.Label(control_frame, text='選択範囲').grid(row=4, column=0, sticky='w')
        self.selection_label = tk.Label(control_frame, text='-', anchor='w')
        self.selection_label.grid(row=4, column=1, sticky='w')

        tk.Label(control_frame, text='ラベル').grid(row=5, column=0, sticky='w')
        self.label_entry = tk.Entry(control_frame, width=20)
        self.label_entry.grid(row=5, column=1, sticky='w')

        tk.Button(control_frame, text='追加', command=self.add_selection).grid(row=6, column=0, columnspan=2, pady=(8, 4), sticky='ew')
        tk.Button(control_frame, text='保存', command=self.save_labels).grid(row=7, column=0, columnspan=1, sticky='ew')
        tk.Button(control_frame, text='JSON 読み込み', command=self.load_labels_from_json).grid(row=7, column=1, sticky='ew')

        tk.Label(control_frame, text='ラベル一覧').grid(row=8, column=0, columnspan=2, sticky='w', pady=(12, 0))
        self.listbox = tk.Listbox(control_frame, width=34, height=14)
        self.listbox.grid(row=9, column=0, columnspan=2, sticky='ew')
        tk.Button(control_frame, text='削除', command=self.delete_selection).grid(row=10, column=0, columnspan=2, pady=(4, 0), sticky='ew')

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.canvas.bind('<Configure>', self.on_canvas_resize)
        self.canvas.bind('<ButtonPress-1>', self.on_mouse_down)
        self.canvas.bind('<B1-Motion>', self.on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_mouse_up)
        self.canvas.bind('<Motion>', self.on_mouse_move)
        self.canvas.bind('<Leave>', self.on_mouse_leave)
        self.listbox.bind('<<ListboxSelect>>', self.on_list_select)

    def load_default_image(self):
        default_path = Path(DEFAULT_IMAGE)
        if default_path.exists():
            self.load_image(str(default_path))

    def open_image(self):
        path = filedialog.askopenfilename(
            title='画像を選択',
            filetypes=[('PNG files', '*.png'), ('JPEG files', '*.jpg;*.jpeg'), ('All files', '*.*')]
        )
        if path:
            self.load_image(path)

    def load_image(self, path):
        try:
            self.base_image = Image.open(path).convert('RGBA')
        except Exception as exc:
            messagebox.showerror('読み込みエラー', f'画像を読み込めませんでした: {exc}')
            return

        self.image_path = Path(path)
        self.image_label.config(text=self.image_path.name)
        self.scale_factor = 1.0
        self.display_image = self.base_image
        self.update_display_image()
        self.redraw_selections()

    def update_display_image(self):
        if self.base_image is None:
            return

        canvas_width = max(1, self.canvas.winfo_width())
        canvas_height = max(1, self.canvas.winfo_height())
        if canvas_width == 1 and canvas_height == 1:
            canvas_width = self.base_image.width
            canvas_height = self.base_image.height

        scale = min(canvas_width / self.base_image.width, canvas_height / self.base_image.height)
        if scale <= 0:
            scale = 1.0

        self.scale_factor = scale
        new_display_width = max(1, int(self.base_image.width * scale))
        new_display_height = max(1, int(self.base_image.height * scale))
        if new_display_width == self.display_width and new_display_height == self.display_height:
            return

        self.display_width = new_display_width
        self.display_height = new_display_height
        self.display_image = self.base_image.resize((self.display_width, self.display_height), Image.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(self.display_image)

        self.canvas.delete('all')
        self.canvas.config(width=self.display_width, height=self.display_height)
        self.canvas.create_image(0, 0, anchor='nw', image=self.tk_image, tags='base_image')
        self.draw_grid()

    def canvas_to_image_coords(self, x, y):
        if self.scale_factor <= 0:
            return 0, 0
        image_x = int(min(max(x, 0), self.display_width) / self.scale_factor)
        image_y = int(min(max(y, 0), self.display_height) / self.scale_factor)
        image_x = min(image_x, self.base_image.width)
        image_y = min(image_y, self.base_image.height)
        return image_x, image_y

    def image_to_canvas_coords(self, x, y):
        return int(x * self.scale_factor), int(y * self.scale_factor)

    def on_canvas_resize(self, event):
        if self.base_image is None:
            return
        if self.resize_job is not None:
            self.root.after_cancel(self.resize_job)
        self.resize_job = self.root.after(80, self._resize_canvas)

    def _resize_canvas(self):
        self.resize_job = None
        self.update_display_image()
        self.redraw_selections()

    def snap_to_grid(self, x, y):
        step = self.grid_step
        if step <= 0:
            return x, y
        return (x // step) * step, (y // step) * step

    def update_grid_step(self):
        try:
            step = clamp_even(int(self.grid_step_var.get()))
        except ValueError:
            step = 2
        self.grid_step = step
        self.grid_step_var.set(str(self.grid_step))
        self.draw_grid()
        self.redraw_selections()

    def draw_grid(self):
        self.canvas.delete('grid')
        if self.base_image is None:
            return
        step = self.grid_step
        if step <= 0:
            return
        for x in range(0, self.base_image.width + 1, step):
            cx0, cy0 = self.image_to_canvas_coords(x, 0)
            cx1, cy1 = self.image_to_canvas_coords(x, self.base_image.height)
            self.canvas.create_line(cx0, cy0, cx1, cy1, fill='#888888', tags='grid')
        for y in range(0, self.base_image.height + 1, step):
            cx0, cy0 = self.image_to_canvas_coords(0, y)
            cx1, cy1 = self.image_to_canvas_coords(self.base_image.width, y)
            self.canvas.create_line(cx0, cy0, cx1, cy1, fill='#888888', tags='grid')

    def draw_hover_point(self, x, y):
        self.canvas.delete('hover')
        radius = 6
        self.canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            outline='cyan', width=1, tags='hover'
        )
        self.canvas.create_line(x - radius, y, x + radius, y, fill='cyan', width=1, tags='hover')
        self.canvas.create_line(x, y - radius, x, y + radius, fill='cyan', width=1, tags='hover')

    def clear_hover(self):
        self.canvas.delete('hover')

    def on_mouse_down(self, event):
        if self.base_image is None:
            return
        ix, iy = self.canvas_to_image_coords(event.x, event.y)
        x, y = self.snap_to_grid(ix, iy)
        x = max(0, min(self.base_image.width, x))
        y = max(0, min(self.base_image.height, y))
        self.start_x, self.start_y = x, y
        self.current_selection = (x, y, 0, 0)
        self.update_selection_display(x, y, 0, 0)
        if self.current_rect_id:
            self.canvas.delete(self.current_rect_id)
            self.current_rect_id = None

    def on_mouse_drag(self, event):
        if self.start_x is None or self.start_y is None:
            return
        ix, iy = self.canvas_to_image_coords(event.x, event.y)
        x, y = self.snap_to_grid(ix, iy)
        x = max(0, min(self.base_image.width, x))
        y = max(0, min(self.base_image.height, y))
        left = min(self.start_x, x)
        top = min(self.start_y, y)
        right = max(self.start_x, x)
        bottom = max(self.start_y, y)
        width = max(2, right - left)
        height = max(2, bottom - top)
        self.current_selection = (left, top, width, height)
        self.update_selection_display(left, top, width, height)
        if self.current_rect_id:
            self.canvas.delete(self.current_rect_id)
        x0, y0 = self.image_to_canvas_coords(left, top)
        x1, y1 = self.image_to_canvas_coords(left + width, top + height)
        self.current_rect_id = self.canvas.create_rectangle(
            x0, y0, x1, y1,
            outline='red', width=2, dash=(4, 2), tags='current_selection'
        )

    def on_mouse_move(self, event):
        if self.base_image is None:
            return
        ix, iy = self.canvas_to_image_coords(event.x, event.y)
        x, y = self.snap_to_grid(ix, iy)
        x = max(0, min(self.base_image.width, x))
        y = max(0, min(self.base_image.height, y))
        cx, cy = self.image_to_canvas_coords(x, y)
        self.draw_hover_point(cx, cy)

    def on_mouse_leave(self, event):
        self.clear_hover()

    def on_mouse_up(self, event):
        if self.current_selection is None:
            return
        x, y, width, height = self.current_selection
        if width < 2 or height < 2:
            self.current_selection = None
            self.update_selection_display(0, 0, 0, 0)
            if self.current_rect_id:
                self.canvas.delete(self.current_rect_id)
                self.current_rect_id = None
            return
        self.update_selection_display(x, y, width, height)

    def update_selection_display(self, x, y, width, height):
        self.selection_label.config(text=f'{x},{y}  {width}x{height}')

    def add_selection(self):
        if self.current_selection is None:
            messagebox.showinfo('選択なし', '先に範囲をドラッグして選択してください。')
            return
        label = self.label_entry.get().strip()
        if not label:
            messagebox.showinfo('ラベルなし', 'ラベルを入力してください。')
            return
        x, y, width, height = self.current_selection
        entry = {'label': label, 'x': x, 'y': y, 'w': width, 'h': height}
        self.selections.append(entry)
        self.listbox.insert(tk.END, f"{label}: {x},{y} {width}x{height}")
        self.label_entry.delete(0, tk.END)
        self.current_selection = None
        if self.current_rect_id:
            self.canvas.delete(self.current_rect_id)
            self.current_rect_id = None
        self.active_selection_index = len(self.selections) - 1
        self.redraw_selections()

    def on_list_select(self, event):
        index = self.listbox.curselection()
        if not index:
            self.active_selection_index = None
        else:
            self.active_selection_index = index[0]
        self.redraw_selections()

    def redraw_selections(self):
        self.canvas.delete('selection')
        self.canvas.delete('active_selection')
        for index, sel in enumerate(self.selections):
            x, y, w, h = sel['x'], sel['y'], sel['w'], sel['h']
            x0, y0 = self.image_to_canvas_coords(x, y)
            x1, y1 = self.image_to_canvas_coords(x + w, y + h)
            self.canvas.create_rectangle(
                x0, y0, x1, y1,
                outline='lime', width=2, tags='selection'
            )
            self.canvas.create_text(
                x0 + 4, y0 + 4,
                text=sel['label'], anchor='nw', fill='yellow', font=('Helvetica', 10, 'bold'), tags='selection'
            )

        if self.active_selection_index is not None and 0 <= self.active_selection_index < len(self.selections):
            active = self.selections[self.active_selection_index]
            x, y, w, h = active['x'], active['y'], active['w'], active['h']
            x0, y0 = self.image_to_canvas_coords(x, y)
            x1, y1 = self.image_to_canvas_coords(x + w, y + h)
            self.canvas.create_rectangle(
                x0, y0, x1, y1,
                outline='red', width=3, tags='active_selection'
            )
            self.canvas.create_text(
                x0 + 4, y0 + 4,
                text=active['label'], anchor='nw', fill='red', font=('Helvetica', 10, 'bold'), tags='active_selection'
            )

    def delete_selection(self):
        index = self.listbox.curselection()
        if not index:
            messagebox.showinfo('選択なし', 'リストから削除するラベルを選択してください。')
            return
        pos = index[0]
        self.listbox.delete(pos)
        del self.selections[pos]
        if self.active_selection_index == pos:
            self.active_selection_index = None
        elif self.active_selection_index is not None and self.active_selection_index > pos:
            self.active_selection_index -= 1
        self.redraw_selections()

    def save_labels(self):
        if not self.selections:
            messagebox.showinfo('保存なし', '保存するラベルがありません。')
            return
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = Path(OUTPUT_DIR) / f'{self.image_path.stem}_labels.json'
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(self.selections, f, ensure_ascii=False, indent=2)
        messagebox.showinfo('保存完了', f'ラベルを {output_path} に保存しました。')

    def load_labels_from_json(self):
        path = filedialog.askopenfilename(
            title='JSON を選択',
            filetypes=[('JSON files', '*.json'), ('All files', '*.*')]
        )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as exc:
            messagebox.showerror('読み込みエラー', f'JSON を読み込めませんでした: {exc}')
            return

        if not isinstance(data, list):
            messagebox.showerror('形式エラー', 'JSON は配列形式である必要があります。')
            return

        loaded = []
        for item in data:
            if not isinstance(item, dict):
                continue
            if not all(k in item for k in ('label', 'x', 'y', 'w', 'h')):
                continue
            try:
                loaded.append({
                    'label': str(item['label']),
                    'x': int(item['x']),
                    'y': int(item['y']),
                    'w': int(item['w']),
                    'h': int(item['h']),
                })
            except (TypeError, ValueError):
                continue

        if not loaded:
            messagebox.showerror('形式エラー', '有効なラベルデータが見つかりませんでした。')
            return

        self.selections = loaded
        self.listbox.delete(0, tk.END)
        for sel in self.selections:
            self.listbox.insert(tk.END, f"{sel['label']}: {sel['x']},{sel['y']} {sel['w']}x{sel['h']}")
        self.redraw_selections()
        messagebox.showinfo('読み込み完了', f'{len(self.selections)} 件のラベルを読み込みました。')


if __name__ == '__main__':
    root = tk.Tk()
    app = GridLabelerApp(root)
    root.mainloop()
