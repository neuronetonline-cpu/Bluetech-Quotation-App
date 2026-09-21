
import os, sqlite3, subprocess, sys
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether
from reportlab.lib.units import mm

APP_DIR = os.path.join(os.path.expanduser("~"), "BluetechQuotationApp")
os.makedirs(APP_DIR, exist_ok=True)
DB = os.path.join(APP_DIR, "quotations.db")
PDF_DIR = os.path.join(APP_DIR, "Quotations")
os.makedirs(PDF_DIR, exist_ok=True)

DEFAULT_PRODUCTS = [
    "MOTHER BOARD","PROCESSOR","CPU FAN","RAMS","PSU","CASING","CASING FANS",
    "SSD","HDD","VGA (used -03m)","MONITOR (used-03m)","ALL CABLES",
    "MOUSE","KEYBOARD","SPEAKER","WIFI ADAPTER"
]

def db():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS quotations(
        id INTEGER PRIMARY KEY AUTOINCREMENT, qno TEXT, customer TEXT, phone TEXT,
        date TEXT, profit REAL, warranty180 REAL, warranty360 REAL, weight REAL,
        created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT, quotation_id INTEGER,
        product TEXT, description TEXT, qty REAL, cost REAL, sell REAL)""")
    c.commit()
    return c

def next_qno():
    c = db()
    n = c.execute("SELECT COUNT(*) FROM quotations").fetchone()[0] + 1
    c.close()
    return f"QT-{datetime.now():%Y%m%d}-{n:04d}"

def money(v):
    return f"LKR {v:,.2f}"

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Bluetech Computers - Desktop Quotation")
        self.root.geometry("1250x780")
        self.root.minsize(1050, 680)
        self.rows = []
        self.build()

    def build(self):
        top = ttk.Frame(self.root, padding=12); top.pack(fill="x")
        ttk.Label(top, text="BLUETECH COMPUTERS", font=("Segoe UI", 20, "bold")).pack(side="left")
        ttk.Button(top, text="Quotation History", command=self.history).pack(side="right", padx=5)
        ttk.Button(top, text="New Quotation", command=self.new_quote).pack(side="right")

        info = ttk.LabelFrame(self.root, text="Customer / Quotation", padding=10)
        info.pack(fill="x", padx=12, pady=5)
        self.qno = tk.StringVar(value=next_qno())
        self.customer = tk.StringVar()
        self.phone = tk.StringVar()
        self.qdate = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        fields = [("Quotation No.", self.qno), ("Customer Name", self.customer),
                  ("WhatsApp / Phone", self.phone), ("Date", self.qdate)]
        for i,(lab,var) in enumerate(fields):
            ttk.Label(info,text=lab).grid(row=0,column=i*2,sticky="w",padx=5)
            ttk.Entry(info,textvariable=var,width=25).grid(row=0,column=i*2+1,sticky="ew",padx=5)
        for i in range(8): info.columnconfigure(i, weight=1)

        box = ttk.LabelFrame(self.root, text="Quotation Items (Cost and Profit are INTERNAL ONLY)", padding=8)
        box.pack(fill="both", expand=True, padx=12, pady=5)

        heads = ["PRODUCT","DESCRIPTION","QTY","COST (INTERNAL)","SELLING PRICE","REMOVE"]
        for j,h in enumerate(heads):
            ttk.Label(box,text=h,font=("Segoe UI",9,"bold")).grid(row=0,column=j,padx=3,pady=4,sticky="ew")
        self.table = ttk.Frame(box); self.table.grid(row=1,column=0,columnspan=6,sticky="nsew")
        box.rowconfigure(1,weight=1)
        for j,w in enumerate([23,34,10,18,18,10]): box.columnconfigure(j,weight=1,minsize=w*8)

        self.rows = []
        for p in DEFAULT_PRODUCTS: self.add_row(p, silent=True)

        controls = ttk.Frame(self.root,padding=8); controls.pack(fill="x",padx=12)
        ttk.Button(controls,text="+ ADD PRODUCT / ROW",command=lambda:self.add_row("")).pack(side="left")

        self.total_cost = tk.StringVar(value="LKR 0.00")
        self.total_sell = tk.StringVar(value="LKR 0.00")
        self.profit = tk.StringVar(value="0")
        self.w180 = tk.StringVar(value="0")
        self.w360 = tk.StringVar(value="0")
        self.weight = tk.StringVar(value="0")

        calc = ttk.LabelFrame(self.root,text="Internal Calculation",padding=10); calc.pack(fill="x",padx=12,pady=5)
        labels = [("Total Cost",self.total_cost),("Requested Profit",self.profit),
                  ("Final Selling Price",self.total_sell),("180 Days Warranty",self.w180),
                  ("360 Days Warranty",self.w360),("Weight (KG)",self.weight)]
        for i,(lab,var) in enumerate(labels):
            ttk.Label(calc,text=lab).grid(row=0,column=i,padx=5)
            e=ttk.Entry(calc,textvariable=var,width=17)
            e.grid(row=1,column=i,padx=5)
            if lab=="Requested Profit": e.bind("<KeyRelease>",lambda e:self.recalc())
            if "Warranty" in lab or lab=="Weight (KG)": e.bind("<KeyRelease>",lambda e:self.recalc())
        ttk.Button(calc,text="CALCULATE",command=self.recalc).grid(row=1,column=6,padx=8)

        actions = ttk.Frame(self.root,padding=10); actions.pack(fill="x",padx=12)
        ttk.Button(actions,text="PREVIEW / SAVE PDF",command=self.save_pdf).pack(side="right",padx=5)
        ttk.Button(actions,text="SAVE QUOTATION",command=self.save_quote).pack(side="right",padx=5)
        ttk.Button(actions,text="CLEAR",command=self.new_quote).pack(side="right",padx=5)
        self.recalc()

    def add_row(self, product="", silent=False):
        r = len(self.rows)
        p=tk.StringVar(value=product); d=tk.StringVar(); q=tk.StringVar(value="1"); c=tk.StringVar(value="0"); s=tk.StringVar(value="0")
        widgets=[]
        for j,var in enumerate([p,d,q,c,s]):
            e=ttk.Entry(self.table,textvariable=var)
            e.grid(row=r,column=j,padx=2,pady=2,sticky="ew")
            widgets.append(e)
            e.bind("<KeyRelease>",lambda e:self.recalc())
        btn=ttk.Button(self.table,text="X",width=5,command=lambda rr=r:self.remove_row(rr))
        btn.grid(row=r,column=5,padx=2)
        self.rows.append((p,d,q,c,s,widgets,btn))
        if not silent: self.recalc()

    def remove_row(self, idx):
        if idx >= len(self.rows): return
        for w in self.rows[idx][5]: w.destroy()
        self.rows[idx][6].destroy()
        self.rows.pop(idx)
        # rebuild grid positions
        for r,row in enumerate(self.rows):
            for j,w in enumerate(row[5]): w.grid_configure(row=r,column=j)
            row[6].grid_configure(row=r,column=5)
        self.recalc()

    def num(self,x):
        try:return float(str(x).replace(",","").replace("LKR","").strip() or 0)
        except:return 0

    def recalc(self):
        cost=sell=0
        for p,d,q,c,s,*_ in self.rows:
            qty=self.num(q.get()); cost += qty*self.num(c.get()); sell += qty*self.num(s.get())
        self.total_cost.set(money(cost)); self.total_sell.set(money(sell))
        try:
            self.profit.set(str(round(sell-cost,2)))
        except: pass

    def collect_items(self):
        out=[]
        for p,d,q,c,s,*_ in self.rows:
            if p.get().strip() and self.num(q.get())>0:
                out.append((p.get().strip(),d.get().strip(),self.num(q.get()),self.num(c.get()),self.num(s.get())))
        return out

    def save_quote(self):
        items=self.collect_items()
        if not self.customer.get().strip(): messagebox.showwarning("Customer","Enter customer name."); return
        self.recalc()
        c=db()
        c.execute("INSERT INTO quotations(qno,customer,phone,date,profit,warranty180,warranty360,weight,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                  (self.qno.get(),self.customer.get(),self.phone.get(),self.qdate.get(),self.num(self.profit.get()),
                   self.num(self.w180.get()),self.num(self.w360.get()),self.num(self.weight.get()),datetime.now().isoformat()))
        qid=c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.executemany("INSERT INTO items(quotation_id,product,description,qty,cost,sell) VALUES(?,?,?,?,?,?)",
                      [(qid,*x) for x in items])
        c.commit(); c.close()
        messagebox.showinfo("Saved",f"Quotation {self.qno.get()} saved.")
        return qid

    def save_pdf(self):
        self.recalc()
        items=self.collect_items()
        if not self.customer.get().strip(): messagebox.showwarning("Customer","Enter customer name."); return
        filename=os.path.join(PDF_DIR,f"{self.qno.get()}.pdf")
        styles=getSampleStyleSheet()
        title=ParagraphStyle("title",parent=styles["Title"],fontSize=18,leading=22,alignment=TA_CENTER)
        small=ParagraphStyle("small",parent=styles["BodyText"],fontSize=8,leading=10)
        normal=ParagraphStyle("normal",parent=styles["BodyText"],fontSize=9,leading=12)
        doc=SimpleDocTemplate(filename,pagesize=A4,rightMargin=12*mm,leftMargin=12*mm,topMargin=12*mm,bottomMargin=12*mm)
        story=[Paragraph("BLUETECH COMPUTERS",title),
               Paragraph("Computer Sales | Repairs | Upgrades",normal),Spacer(1,5),
               Paragraph(f"<b>QUOTATION</b> &nbsp;&nbsp; No: {self.qno.get()} &nbsp;&nbsp; Date: {self.qdate.get()}",normal),
               Paragraph(f"<b>Customer:</b> {self.customer.get()} &nbsp;&nbsp; <b>Phone:</b> {self.phone.get()}",normal),Spacer(1,8)]
        data=[["PRODUCT","PRODUCT DESCRIPTION","QTY"]]
        for p,d,q,c,s in items:
            data.append([p,d,str(int(q) if q.is_integer() else q)])
        t=Table(data,colWidths=[55*mm,105*mm,18*mm],repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1F4E78")),
                               ("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
                               ("FONTSIZE",(0,0),(-1,-1),8),("GRID",(0,0),(-1,-1),0.35,colors.grey),
                               ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F5F7FA")])]))
        story.append(t); story.append(Spacer(1,10))
        story.append(Paragraph(f"<b>WITH 180 DAYS HARDWARE WARRANTY</b> &nbsp;&nbsp; {money(self.num(self.w180.get()))}",normal))
        story.append(Spacer(1,4))
        story.append(Paragraph(f"<b>WITH 360 DAYS HARDWARE WARRANTY</b> &nbsp;&nbsp; {money(self.num(self.w360.get()))}",normal))
        story.append(Spacer(1,12))
        story.append(Paragraph("Thank you for your business.",normal))
        story.append(Spacer(1,5))
        story.append(Paragraph("Facebook | TikTok | Google Reviews",small))
        doc.build(story)
        try:
            if sys.platform.startswith("win"): os.startfile(filename)
            else: subprocess.Popen(["xdg-open",filename])
        except: pass
        messagebox.showinfo("PDF Created",f"PDF created:\n{filename}\n\nUse the PDF viewer's Share/Send option to send it on WhatsApp.")
        return filename

    def new_quote(self):
        # recreate window for a clean quotation
        for w in self.root.winfo_children(): w.destroy()
        self.rows=[]
        self.build()

    def history(self):
        win=tk.Toplevel(self.root); win.title("Quotation History"); win.geometry("850x500")
        tree=ttk.Treeview(win,columns=("q","customer","phone","date","profit"),show="headings")
        for c,h in zip(("q","customer","phone","date","profit"),("Quotation No.","Customer","Phone","Date","Internal Profit")):
            tree.heading(c,text=h); tree.column(c,width=150)
        tree.pack(fill="both",expand=True,padx=10,pady=10)
        c=db()
        for row in c.execute("SELECT qno,customer,phone,date,profit FROM quotations ORDER BY id DESC"):
            tree.insert("", "end", values=row)
        c.close()
        ttk.Button(win,text="Close",command=win.destroy).pack(pady=5)

if __name__=="__main__":
    root=tk.Tk()
    App(root)
    root.mainloop()
