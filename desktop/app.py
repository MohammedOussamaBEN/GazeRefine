"""Native Tk desktop application. Run: python -m desktop.app"""
from __future__ import annotations
import csv
import json
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
from gazerefine.interactive import AppConfig, CPUInference, load_image, read_fixations, samples_to_fixations
from .trackers import EyeTraxTracker, TobiiTracker


class GazeRefineApp:
    def __init__(self, root):
        self.root = root
        self.engine = CPUInference()
        self.events = queue.Queue()
        self.image = self.display = self.result = None
        self.image_path = None
        self.points, self.samples = [], []
        self.tracker = None
        self.busy = False
        self.rect = (0,0,1,1)
        root.title("GazeRefine | Local CPU segmentation")
        root.geometry("1280x850")
        root.minsize(950,650)
        root.configure(bg="#101a24")
        style = ttk.Style(); style.theme_use("clam")
        style.configure("TFrame", background="#101a24")
        style.configure("TLabel", background="#101a24", foreground="#e8eff6", font=("Segoe UI",10))
        style.configure("TButton", font=("Segoe UI",10), padding=7)
        bar = ttk.Frame(root, padding=16); bar.pack(fill="x")
        ttk.Label(bar,text="GazeRefine",font=("Segoe UI",22,"bold")).pack(side="left")
        ttk.Label(bar,text="  Expert gaze → frozen features → segmentation  |  CPU").pack(side="left")
        toolbar = ttk.Frame(root, padding=(16,0,16,10)); toolbar.pack(fill="x")
        for label, command in [("Open image / DICOM",self.open_image),("Import fixation CSV",self.import_csv),
                               ("Undo point",self.undo),("Clear gaze",self.clear),("Save outputs",self.save)]:
            ttk.Button(toolbar,text=label,command=command).pack(side="left",padx=(0,7))
        settings = ttk.Frame(root,padding=(16,0,16,10)); settings.pack(fill="x")
        self.modality = tk.StringVar(value="colonoscopy")
        self.resolution = tk.StringVar(value="384")
        self.weighted = tk.BooleanVar(value=True)
        self.duration = tk.StringVar(value="200")
        self.csv_units = tk.StringVar(value="normalized")
        self.view = tk.StringVar(value="Image + gaze")
        for label,var,values,width in [("Modality",self.modality,["colonoscopy","mri"],14),
                                       ("Input pixels",self.resolution,["384","592","1184"],7),
                                       ("CSV coordinates",self.csv_units,["normalized","pixels"],12),
                                       ("View",self.view,["Image + gaze","Mask overlay","Binary mask","Gaze prior"],15)]:
            ttk.Label(settings,text=label+" ").pack(side="left")
            box=ttk.Combobox(settings,textvariable=var,values=values,width=width,state="readonly")
            box.pack(side="left",padx=(0,12));box.bind("<<ComboboxSelected>>",lambda _:self.redraw())
        ttk.Checkbutton(settings,text="Duration weights",variable=self.weighted).pack(side="left")
        options=ttk.Frame(root,padding=(16,0,16,10));options.pack(fill="x")
        ttk.Label(options,text="Click duration (ms)").pack(side="left")
        ttk.Entry(options,textvariable=self.duration,width=7).pack(side="left",padx=8)
        self.source=tk.StringVar(value="EyeTrax webcam")
        ttk.Combobox(options,textvariable=self.source,values=["EyeTrax webcam","Tobii Pro hardware"],state="readonly",width=22).pack(side="left",padx=8)
        ttk.Button(options,text="Start gaze capture",command=self.start_tracker).pack(side="left",padx=4)
        ttk.Button(options,text="Stop / make fixations",command=self.stop_tracker).pack(side="left",padx=4)
        self.run_button=ttk.Button(options,text="Run on CPU",command=self.predict);self.run_button.pack(side="right")
        self.canvas=tk.Canvas(root,bg="#080f17",highlightthickness=0,cursor="crosshair")
        self.canvas.pack(fill="both",expand=True,padx=16)
        self.canvas.bind("<Configure>",lambda _:self.redraw())
        self.canvas.bind("<Button-1>",self.click)
        self.status=tk.StringVar(value="Open an image, then add or import gaze. 384/592 are previews; 1184 is full resolution.")
        ttk.Label(root,textvariable=self.status,padding=12,wraplength=1200).pack(fill="x")
        ttk.Label(root,text="Research prototype. Validate masks before use. Webcam gaze is not a substitute for expert eye-tracker measurements.",padding=(12,0,12,10)).pack(fill="x")
        root.protocol("WM_DELETE_WINDOW",self.close)
        root.after(50,self.poll)

    def error(self, exc):
        messagebox.showerror("GazeRefine",str(exc),parent=self.root)

    def open_image(self):
        if self.busy or self.tracker:
            return self.error("Stop capture and wait for inference before changing image.")
        path=filedialog.askopenfilename(filetypes=[("Images and DICOM","*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.dcm"),("All files","*.*")])
        if not path:return
        try:
            self.image=load_image(path);self.image_path=path;self.points=[];self.samples=[];self.result=None
            self.view.set("Image + gaze");self.redraw();self.status.set(f"{Path(path).name} | {self.image.width} × {self.image.height}. Click the target or import expert gaze.")
        except Exception as exc:self.error(exc)

    def redraw(self):
        self.canvas.delete("all")
        if self.image is None:
            self.canvas.create_text(self.canvas.winfo_width()/2,self.canvas.winfo_height()/2,text="Open a medical image to begin",fill="#91a7b9",font=("Segoe UI",20));return
        choices={"Mask overlay":"overlay","Binary mask":"mask","Gaze prior":"prior"}
        shown=self.result[choices[self.view.get()]] if self.result and self.view.get() in choices else self.image
        cw,ch=max(1,self.canvas.winfo_width()),max(1,self.canvas.winfo_height())
        scale=min(cw/shown.width,ch/shown.height)
        w,h=max(1,round(shown.width*scale)),max(1,round(shown.height*scale));x,y=(cw-w)/2,(ch-h)/2
        self.rect=(x,y,w,h);self.photo=ImageTk.PhotoImage(shown.resize((w,h),Image.Resampling.LANCZOS))
        self.canvas.create_image(x,y,anchor="nw",image=self.photo)
        if self.view.get()=="Image + gaze":
            for i,(px,py,_) in enumerate(self.points):
                xx,yy=x+px*w,y+py*h
                self.canvas.create_oval(xx-5,yy-5,xx+5,yy+5,fill="#00dfc4",outline="#071b22")
                self.canvas.create_text(xx+9,yy-9,text=str(i+1),fill="white",anchor="sw")

    def click(self,event):
        if self.image is None or self.busy or self.tracker:return
        x,y,w,h=self.rect;px,py=(event.x-x)/w,(event.y-y)/h
        if 0<=px<=1 and 0<=py<=1:
            try:
                duration=float(self.duration.get())
                if duration<=0:raise ValueError("Duration must be positive.")
                self.points.append([px,py,duration]);self.result=None;self.view.set("Image + gaze");self.redraw()
                self.status.set(f"{len(self.points)} fixation prompts. Manual points are simulated gaze, not recorded expert observations.")
            except ValueError as exc:self.error(exc)

    def import_csv(self):
        if self.image is None:return self.error("Open an image first.")
        if self.busy or self.tracker:return
        path=filedialog.askopenfilename(filetypes=[("Fixation CSV","*.csv *.tsv *.txt")])
        if path:
            try:
                self.points=read_fixations(path,*self.image.size,coordinates=self.csv_units.get(),image_name=Path(self.image_path).name)
                self.result=None;self.view.set("Image + gaze");self.redraw();self.status.set(f"Imported {len(self.points)} fixation rows.")
            except Exception as exc:self.error(exc)

    def undo(self):
        if self.busy or self.tracker:return
        if self.points:self.points.pop();self.result=None;self.redraw()

    def clear(self):
        if self.busy or self.tracker:return
        self.points=[];self.result=None;self.view.set("Image + gaze");self.redraw()

    def start_tracker(self):
        if self.image is None:return self.error("Open an image first.")
        if self.tracker or self.busy:return
        # Require matching display coordinates for the calibrated primary monitor.
        if not messagebox.askokcancel("Gaze capture","Use the primary monitor at 100% OS scaling. Keep this window still. EyeTrax opens its calibration targets; Tobii must be calibrated in Eye Tracker Manager. Start capture?",parent=self.root):return
        self.samples=[]
        callback=lambda x,y,t:self.events.put(("sample",(x,y,t)))
        error=lambda msg:self.events.put(("tracker_error",msg))
        self.tracker=EyeTraxTracker(callback,error) if self.source.get().startswith("EyeTrax") else TobiiTracker(callback,error,self.root.winfo_screenwidth(),self.root.winfo_screenheight())
        try:
            self.tracker.start();self.status.set("Gaze capture active / calibrating. Look at the target, then press Stop.")
        except Exception as exc:self.tracker=None;self.error(exc)

    def stop_tracker(self):
        if self.tracker:
            self.tracker.stop();self.tracker=None
            fixation=samples_to_fixations(self.samples)
            self.points.extend(fixation);self.result=None;self.view.set("Image + gaze");self.redraw()
            self.status.set(f"Captured {len(self.samples)} samples; added {len(fixation)} dwell groups (≥100 ms). Raw samples are saved with outputs.")

    def predict(self):
        if self.image is None or not self.points:return self.error("Open an image and provide gaze first.")
        if self.busy or self.tracker:return self.error("Stop gaze capture before inference.")
        config=AppConfig(modality=self.modality.get(),resolution=int(self.resolution.get()),duration_weighted=self.weighted.get())
        image=self.image.copy();points=[p[:] for p in self.points]
        self.busy=True;self.run_button.state(["disabled"]);self.status.set("Running on CPU. First run loads/downloads DINOv3 weights; full resolution can take several minutes.")
        def worker():
            try:self.events.put(("result",self.engine.predict(image,points,config)))
            except Exception as exc:self.events.put(("inference_error",str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        for _ in range(1000):
            try:kind,value=self.events.get_nowait()
            except queue.Empty:break
            if kind=="sample" and self.tracker:
                x,y,t=value;rx,ry,w,h=self.rect
                px=(x-self.canvas.winfo_rootx()-rx)/w;py=(y-self.canvas.winfo_rooty()-ry)/h
                self.samples.append([px,py,t])
            elif kind=="result":
                self.result=value;self.busy=False;self.run_button.state(["!disabled"]);self.view.set("Mask overlay");self.redraw()
                m=value["metadata"];self.status.set(f"Done in {m['seconds_including_model_load']:.1f}s | CPU | {m['resolution']} px | {'Preview; not benchmark settings' if m['preview'] else 'Full resolution'}")
            elif kind in ("tracker_error","inference_error"):
                if kind=="tracker_error" and self.tracker:self.tracker.stop();self.tracker=None
                self.busy=False;self.run_button.state(["!disabled"]);self.status.set(value);self.error(value)
        self.root.after(50,self.poll)

    def save(self):
        if self.result is None:return self.error("Run segmentation first.")
        path=filedialog.askdirectory(title="Save output folder")
        if not path:return
        p=Path(path)
        for key in ("mask","overlay","prior"):self.result[key].save(p/f"gazerefine_{key}.png")
        (p/"gazerefine_settings.json").write_text(json.dumps(self.result["metadata"],indent=2))
        for name,rows,columns in [("fixations",self.points,["x","y","duration"]),("samples",self.samples,["x","y","timestamp_ms"])]:
            with (p/f"gazerefine_{name}.csv").open("w",newline="") as f:
                writer=csv.writer(f);writer.writerow(columns);writer.writerows(rows)
        self.status.set(f"Saved masks, overlays, gaze and configuration to {p}")

    def close(self):
        if self.tracker:self.tracker.stop()
        self.root.destroy()


def main():
    root=tk.Tk();GazeRefineApp(root);root.mainloop()


if __name__=="__main__":main()
