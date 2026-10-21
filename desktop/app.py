"""Native Tk desktop application. Run: python -m desktop.app"""
from __future__ import annotations
import csv
import json
import queue
import threading
import sys
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
        self.browser_server = None
        self.busy = False
        self.rect = (0,0,1,1)
        root.title("GazeRefine | Local CPU segmentation")
        root.geometry("1280x850")
        root.minsize(950,650)
        root.configure(bg="#f4f6fa")

        style=ttk.Style();style.theme_use("clam")

        style.configure("TFrame",background="#f4f6fa")

        style.configure("TLabel",background="#f4f6fa",foreground="#22324b",font=("Segoe UI",10))

        style.configure("TButton",font=("Segoe UI",10),padding=8)

        style.configure("Primary.TButton",background="#2563eb",foreground="white",padding=12)

        style.configure("Section.TLabel",font=("Segoe UI",11,"bold"))

        top=ttk.Frame(root,padding=(22,16));top.pack(fill="x")

        ttk.Label(top,text="GazeRefine Studio",font=("Segoe UI",23,"bold")).pack(side="left")

        ttk.Label(top,text="LOCAL CPU  /  TRAINING-FREE",foreground="#53709a").pack(side="right")

        body=ttk.Frame(root,padding=(18,0,18,0));body.pack(fill="both",expand=True)

        rail=ttk.Frame(body,width=300);rail.pack(side="left",fill="y",padx=(0,16));rail.pack_propagate(False)
        scroll=tk.Canvas(rail,bg="#f4f6fa",highlightthickness=0,width=276)
        scrollbar=ttk.Scrollbar(rail,orient="vertical",command=scroll.yview)
        scrollbar.pack(side="right",fill="y");scroll.pack(side="left",fill="both",expand=True)
        scroll.configure(yscrollcommand=scrollbar.set)
        side=ttk.Frame(scroll,padding=(0,0,10,10));window=scroll.create_window((0,0),window=side,anchor="nw")
        side.bind("<Configure>",lambda _:scroll.configure(scrollregion=scroll.bbox("all")))
        scroll.bind("<Configure>",lambda e:scroll.itemconfigure(window,width=e.width))
        def wheel(event):
            widget=root.winfo_containing(event.x_root,event.y_root)
            if widget and str(widget).startswith(str(rail)):scroll.yview_scroll(-int(event.delta/120),"units")
        root.bind("<MouseWheel>",wheel,add="+")

        viewer=ttk.Frame(body);viewer.pack(side="left",fill="both",expand=True)

        self.modality=tk.StringVar(value="colonoscopy");self.resolution=tk.StringVar(value="384")

        self.weighted=tk.BooleanVar(value=True);self.duration=tk.StringVar(value="200")

        self.csv_units=tk.StringVar(value="normalized");self.view=tk.StringVar(value="Image + gaze")

        self.source=tk.StringVar(value="Browser / RealEye webcam")

        def section(title):ttk.Label(side,text=title,style="Section.TLabel",padding=(0,12,0,6)).pack(anchor="w")

        def button(title,command):ttk.Button(side,text=title,command=command).pack(fill="x",pady=3)

        def select(label,var,values):

            ttk.Label(side,text=label).pack(anchor="w",pady=(6,2))

            box=ttk.Combobox(side,textvariable=var,values=values,state="readonly");box.pack(fill="x")

            box.bind("<<ComboboxSelected>>",lambda _:self.redraw())

        section("01  Image & model")

        button("Open image / DICOM",self.open_image)

        select("Modality",self.modality,["colonoscopy","mri"])

        select("Resolution · 384 / 592 preview",self.resolution,["384","592","1184"])

        section("02  Gaze prompts")

        select("CSV coordinate units",self.csv_units,["normalized","pixels"])

        button("Import fixation CSV",self.import_csv)

        sources=["Browser / RealEye webcam"] if getattr(sys,"frozen",False) else ["Browser / RealEye webcam","EyeTrax webcam","Tobii Pro hardware"]

        select("Capture source",self.source,sources)

        button("Open gaze capture",self.start_tracker)

        button("Stop hardware capture",self.stop_tracker)

        ttk.Label(side,text="Manual point duration (ms)").pack(anchor="w",pady=(6,2))

        ttk.Entry(side,textvariable=self.duration).pack(fill="x")

        row=ttk.Frame(side);row.pack(fill="x",pady=5)

        ttk.Button(row,text="Undo",command=self.undo).pack(side="left",expand=True,fill="x")

        ttk.Button(row,text="Clear",command=self.clear).pack(side="left",expand=True,fill="x")

        ttk.Checkbutton(side,text="Duration-weighted gaze",variable=self.weighted).pack(anchor="w")

        self.counts=tk.StringVar(value="0 raw samples  ·  0 fixation prompts")

        ttk.Label(side,textvariable=self.counts,wraplength=260,foreground="#2563eb",padding=(0,8)).pack(anchor="w")

        self.run_button=ttk.Button(side,text="03  Run segmentation on CPU",command=self.predict,style="Primary.TButton")

        self.run_button.pack(fill="x",pady=5)

        button("Export gaze / save results",self.save)

        bar=ttk.Frame(viewer,padding=(12,8));bar.pack(fill="x")

        ttk.Label(bar,text="IMAGE WORKSPACE",style="Section.TLabel").pack(side="left")

        box=ttk.Combobox(bar,textvariable=self.view,values=["Image + gaze","Mask overlay","Binary mask","Gaze prior"],state="readonly",width=19)

        box.pack(side="right");box.bind("<<ComboboxSelected>>",lambda _:self.redraw())

        self.canvas=tk.Canvas(viewer,bg="#111d2e",highlightthickness=0,cursor="crosshair")

        self.canvas.pack(fill="both",expand=True)

        self.canvas.bind("<Configure>",lambda _:self.redraw());self.canvas.bind("<Button-1>",self.click)

        self.status=tk.StringVar(value="Open an image, then import gaze, capture with your webcam, or click to add a prompt.")

        ttk.Label(root,textvariable=self.status,padding=(20,12),wraplength=1100).pack(fill="x")

        ttk.Label(root,text="Research preview · 1184 px is full resolution · Webcam dwell groups are experimental",padding=(20,0,20,10),foreground="#65758b").pack(fill="x")

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
            if self.browser_server:self.browser_server.set_session(self.image,self.points,Path(path).name)
            self.view.set("Image + gaze");self.redraw();self.status.set(f"{Path(path).name} | {self.image.width} × {self.image.height}. Click the target or import expert gaze.")
        except Exception as exc:self.error(exc)

    def redraw(self):
        self.counts.set(f"{len(self.samples)} raw samples  ·  {len(self.points)} fixation prompts")
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
        self.points=[];self.samples=[];self.result=None;self.view.set("Image + gaze");self.redraw()

    def start_tracker(self):
        if self.image is None:return self.error("Open an image first.")
        if self.tracker or self.busy:return
        if self.source.get().startswith("Browser"):
            return self.open_browser()
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
                self.samples.append([px,py,t]);self.counts.set(f"{len(self.samples)} raw samples · stop capture to derive fixations")
            elif kind=="result":
                self.result=value;self.busy=False;self.run_button.state(["!disabled"]);self.view.set("Mask overlay");self.redraw()
                m=value["metadata"];self.status.set(f"Done in {m['seconds_including_model_load']:.1f}s | CPU | {m['resolution']} px | {'Preview; not benchmark settings' if m['preview'] else 'Full resolution'}")
            elif kind=="browser_capture":
                if self.browser_server and value['revision']==self.browser_server.session_version:
                    self.points=[p[:] for p in value['fixations']];self.samples=value['samples'];self.result=None
                    self.view.set("Image + gaze");self.redraw()
                    self.status.set(f"Received {len(value['samples'])} raw samples and {len(value['fixations'])} fixations. " + ("Ready to run on CPU." if self.points else "No qualifying dwell groups. Adjust dwell settings in the browser and rebuild, or export raw gaze."))
            elif kind in ("tracker_error","inference_error"):
                if kind=="tracker_error" and self.tracker:self.tracker.stop();self.tracker=None
                self.busy=False;self.run_button.state(["!disabled"]);self.status.set(value);self.error(value)
        self.root.after(50,self.poll)

    def save(self):
        if not self.points and not self.samples:return self.error("Collect or import gaze first.")
        path=filedialog.askdirectory(title="Save output folder")
        if not path:return
        p=Path(path)
        if self.result:
            for key in ("mask","overlay","prior"):self.result[key].save(p/f"gazerefine_{key}.png")
            (p/"gazerefine_settings.json").write_text(json.dumps(self.result["metadata"],indent=2))
        for name,rows,columns in [("fixations",self.points,["x","y","duration"]),("samples",self.samples,["x","y","timestamp_ms"])]:
            with (p/f"gazerefine_{name}.csv").open("w",newline="") as f:
                writer=csv.writer(f);writer.writerow(columns);writer.writerows(rows)
        self.status.set(f"Saved masks, overlays, gaze and configuration to {p}")

    def open_browser(self):
        import webbrowser
        from scripts.serve_app import AppServer
        if self.browser_server is None:
            self.browser_server=AppServer(("127.0.0.1",0))
            self.browser_server.engine=self.engine
            self.browser_server.on_capture=lambda data:self.events.put(("browser_capture",data))
            threading.Thread(target=self.browser_server.serve_forever,daemon=True).start()
        if self.image is not None:
            self.browser_server.set_session(self.image,self.points,Path(self.image_path).name if self.image_path else "Desktop image")
        webbrowser.open(f"http://127.0.0.1:{self.browser_server.server_port}")

    def close(self):
        if self.tracker:self.tracker.stop()
        if self.browser_server:
            self.browser_server.shutdown();self.browser_server.server_close()
        self.root.destroy()


def main():
    root=tk.Tk();GazeRefineApp(root);root.mainloop()


if __name__=="__main__":main()
