"""PBS NRP Generator v1.0.4 launcher with cumulative KML + KMZ input."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox

from app import App
from kml_support import read_source


class KMLApp(App):
    def __init__(self, root):
        super().__init__(root)
        root.title('PBS Network Route Plan Generator v1.0.4')
        self.status.set('Pilih file KML atau KMZ untuk memulai')
        self._replace_labels(root)

    def _replace_labels(self, widget):
        try:
            value = widget.cget('text')
            if isinstance(value, str):
                replacement = value.replace('v1.0.3', 'v1.0.4').replace('KMZ', 'KML/KMZ')
                if replacement != value:
                    widget.configure(text=replacement)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._replace_labels(child)

    def open_kmz(self):
        path = filedialog.askopenfilename(
            title='Import Google Earth KML / KMZ',
            filetypes=[('Google Earth KML / KMZ', '*.kml *.kmz'),
                       ('KML', '*.kml'), ('KMZ', '*.kmz')],
        )
        if not path:
            return
        try:
            lines, points = read_source(path)
            self.lines, self.points = lines, points
            self.osm = None
            self.path.set(path)
            self.stats.configure(text=(f'Jalur (LineString)  {len(lines):,}\n'
                                       f'Titik (Point)       {len(points):,}\n'
                                       f'Total geometri     {len(lines)+len(points):,}'))
            self.status.set(f'{os.path.splitext(path)[1][1:].upper()} berhasil dibaca')
            self.draw()
        except (OSError, ValueError) as exc:
            messagebox.showerror('Import gagal', str(exc))


if __name__ == '__main__':
    root = tk.Tk()
    KMLApp(root)
    root.mainloop()
