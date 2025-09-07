import json
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from mpl_toolkits.mplot3d import Axes3D  # import required once at top
from openai import OpenAI

from config import OPENAI_KEY
from rfem_conn import fea_to_rfem
from objects import CrossFrame, Deck, Girder, FEAModel, generate_stations, generate_supports



api_key = OPENAI_KEY
client = OpenAI(api_key=api_key)  # assumes OPENAI_API_KEY in environment

class BridgeUI:
    def __init__(self, root):
        self.root = root
        root.title("Parametric Bridge Generator")
        self.last_fea = None   # holds last generated FEAModel

        # Parameters
        self.num_spans = tk.IntVar(value=1)
        self.span_lengths: list[tk.DoubleVar] = []  # will be filled dynamically
        
        self.num_spans.trace_add("write", lambda *args: self.update_span_fields())

        self.num_girders = tk.IntVar(value=3)
        self.girder_spacing = tk.DoubleVar(value=3.0)
        self.girder_depth = tk.DoubleVar(value=2.0)
        self.web_thickness = tk.DoubleVar(value=0.2)

        self.deck_thickness = tk.DoubleVar(value=0.25)
        self.overhang = tk.DoubleVar(value=0.5)
        self.mesh_size = tk.DoubleVar(value=2.5)
        self.crossframe_spacing = tk.DoubleVar(value=5.0)
        self.flange_width = tk.DoubleVar(value=0.5)
        self.flange_thickness = tk.DoubleVar(value=0.05)
        
        
        self.frm_left = ttk.Frame(self.root)
        self.frm_left.pack(side="left", fill="y", padx=10, pady=10)

        # Number of spans field
        ttk.Label(self.frm_left, text="Number of spans").grid(row=0, column=0, sticky="w")
        tk.Entry(self.frm_left, textvariable=self.num_spans).grid(row=0, column=1)

        self.frm_right = ttk.Frame(root)
        self.frm_right.pack(side="right", fill="both", expand=True)
        
        # placeholder for canvas (3D plot goes here)
        self.canvas_frame = ttk.Frame(self.frm_right)
        self.canvas_frame.pack(side="top", fill="both", expand=True)

        # chat frame at bottom-right
        self.chat_frame = ttk.Frame(self.frm_right, relief="flat", padding=0)
        self.chat_frame.pack(side="bottom", fill="x")
        
        sep = ttk.Separator(self.frm_right, orient="horizontal")
        sep.pack(side="bottom", fill="x")
        # UI layout
        self._build_form()
        self._build_chat()
        self._build_canvas()
        self.last_prompt = None
        self.last_answer = None

    def _build_form(self):
       
        
        # Placeholder frame for span lengths
        self.span_frame = ttk.Frame(self.frm_left)
        self.span_frame.grid(row=1, column=0, columnspan=3, pady=5, sticky="w")

        # Other fields (fixed)
        self.row_offset = 2  # because row 0 & 1 taken
        self.fields = [
            ("Number of girders", self.num_girders),
            ("Girder spacing", self.girder_spacing),
            ("Girder depth", self.girder_depth),
            ("Web thickness", self.web_thickness),
            ("Flange width", self.flange_width),
            ("Flange thickness", self.flange_thickness),
            ("Deck thickness", self.deck_thickness),
            ("Overhang", self.overhang),
            ("Mesh size", self.mesh_size),
            ("Cross-frame spacing", self.crossframe_spacing),
        ]

        for i,(label,var) in enumerate(self.fields, start=self.row_offset):
            ttk.Label(self.frm_left, text=label).grid(row=i, column=0, sticky="w")
            tk.Entry(self.frm_left, textvariable=var).grid(row=i, column=1)

        ttk.Button(self.frm_left, text="Generate", command=self.generate_bridge).grid(
            row=self.row_offset+len(self.fields), column=0, columnspan=2, pady=5
        )
        
        ttk.Button(self.frm_left, text="Export to RFEM", command=self.export_to_rfem).grid(
        row=self.row_offset+len(self.fields)+1, column=0, columnspan=2, pady=5
        )
        
    def _build_chat(self):
        # --- thin separator above chat ---
        sep = ttk.Separator(self.frm_right, orient="horizontal")
        sep.pack(side="bottom", fill="x")

        # --- main chat frame (below 3D canvas) ---
        self.chat_frame = ttk.Frame(self.frm_right, relief="flat", padding=0)
        self.chat_frame.pack(side="bottom", fill="both", expand=True)

        # --- chat history area (with scrollbar) ---
        history_frame = ttk.Frame(self.chat_frame)
        history_frame.pack(side="top", fill="both", expand=True)

        self.chat_canvas = tk.Canvas(history_frame, bg="white", highlightthickness=0)
        self.chat_scrollbar = tk.Scrollbar(history_frame, orient="vertical", command=self.chat_canvas.yview)
        self.chat_history_frame = tk.Frame(self.chat_canvas, bg="white")
        self.chat_window = self.chat_canvas.create_window((0, 0), window=self.chat_history_frame, anchor="nw")

        self.chat_history_frame.bind(
            "<Configure>",
            lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        )

        self.chat_canvas.configure(yscrollcommand=self.chat_scrollbar.set)

        self.chat_canvas.pack(side="left", fill="both", expand=True)
        self.chat_scrollbar.pack(side="right", fill="y")

        # --- entry bar (bottom, fixed) ---
        entry_frame = ttk.Frame(self.chat_frame)
        entry_frame.pack(side="bottom", fill="x")

        self.chat_entry = tk.Entry(entry_frame)
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(5, 5), pady=5)

        send_btn = ttk.Button(entry_frame, text="Send", command=self.run_llm_command)
        send_btn.pack(side="right", padx=(0, 5), pady=5)

        # make Enter key send
        self.chat_entry.bind("<Return>", lambda e: self.run_llm_command())



    
    
        
    def add_chat_message(self, sender, msg, state=None):
        bubble_frame = tk.Frame(self.chat_history_frame, bg="white")

        if sender == "You":
            side = "right"
            bg = "#DCF8C6"
        elif sender == "LLM":
            side = "left"
            bg = "#ECECEC"
        else:
            side = "left"
            bg = "#FFD2D2"

        text = msg
        if sender == "You" and state is not None:
            text = f"{msg}\n\nState: {state}"

        bubble = tk.Label(
            bubble_frame,
            text=text,
            bg=bg,
            padx=10,
            pady=5,
            wraplength=300,
            justify="left"
        )
        bubble.pack()

        # ✅ only use `side`, not anchor
        bubble_frame.pack(pady=2, padx=10, anchor="w" if side == "left" else "e")

        # scroll to bottom
        self.chat_canvas.update_idletasks()
        self.chat_canvas.yview_moveto(1)



                
    def export_to_rfem(self):
        if self.last_fea is None:
            print("⚠️ Please generate the bridge first before exporting.")
            return
        try:
            fea_to_rfem(self.last_fea, model_name="BridgeParametric")
            print("✅ Export successful, check RFEM.")
        except Exception as e:
            print(f"❌ Export failed: {e}")
            
    def update_span_fields(self):
        """Rebuilds entry fields for span lengths based on num_spans."""
        for widget in self.span_frame.winfo_children():
            widget.destroy()

        self.span_lengths = []
        for i in range(self.num_spans.get()):
            var = tk.DoubleVar(value=30.0)  # default span length
            self.span_lengths.append(var)
            ttk.Label(self.span_frame, text=f"Span {i+1} length").grid(row=i, column=0, sticky="w")
            tk.Entry(self.span_frame, textvariable=var).grid(row=i, column=1)

    def update_from_dict(self, params: dict):
        if "span_lengths" in params:
            lengths = params["span_lengths"]
            self.num_spans.set(len(lengths))   # auto-set num_of_spans
            self.update_span_fields()
            for i, val in enumerate(lengths):
                if i < len(self.span_lengths):
                    self.span_lengths[i].set(val)

        # other fields
        mapping = {
            "number_of_girders": self.num_girders,
            "girder_spacing": self.girder_spacing,
            "girder_depth": self.girder_depth,
            "flange_width": self.flange_width,
            "flange_thickness": self.flange_thickness,
            "deck_thickness": self.deck_thickness,
            "overhang": self.overhang,
            "mesh_size": self.mesh_size,
            "crossframe_spacing": self.crossframe_spacing,
        }
        for key, var in mapping.items():
            if key in params:
                var.set(params[key])

    
    def to_llm_dict(self):
        data = {
            "span_lengths": [var.get() for var in self.span_lengths],
            "number_of_girders": self.num_girders.get(),
            "girder_spacing": self.girder_spacing.get(),
            "girder_depth": self.girder_depth.get(),
            "flange_width": self.flange_width.get(),
            "flange_thickness": self.flange_thickness.get(),
            "deck_thickness": self.deck_thickness.get(),
            "overhang": self.overhang.get(),
            "mesh_size": self.mesh_size.get(),
            "crossframe_spacing": self.crossframe_spacing.get(),
        }

        # include analysis results only if available
        if getattr(self.last_fea, "max_deflection", None) is not None:
            data["max_deflection"] = float(self.last_fea.max_deflection)

        return data

    
    
    

    
    

    
    

    
    

    
    

    

    def _build_canvas(self):
        self.fig = plt.figure(figsize=(6,4))
        self.ax = self.fig.add_subplot(111, projection="3d")
        ax = self.ax
                # --- cleanup view ---
        ax.set_axis_off()        # hides all axes, ticks, labels
        ax.grid(False)           # no grid
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_zticks([])
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.canvas_frame)
        self.canvas.get_tk_widget().pack(side="right", fill="both", expand=True)
        
    def generate_bridge(self):
        fea = FEAModel()

        # Collect span lengths
        span_lengths = [var.get() for var in self.span_lengths]
        total_length = sum(span_lengths)

        mesh_size = self.mesh_size.get()
        cross_spacing = self.crossframe_spacing.get()

        fea.flange_thickness = self.flange_thickness.get()
        fea.flange_width = self.flange_width.get()

        # Cross-frame positions (for each span)
        crossframes = []
        x0 = 0
        for L in span_lengths:
            n_frames = int(L / cross_spacing)
            crossframes += [x0 + i*cross_spacing for i in range(1, n_frames)]
            x0 += L

        stations = generate_stations(0, total_length, crossframes, mesh_size)

        # Girders
        girders = [
            Girder(
                id=i,
                depth=self.girder_depth.get(),
                flange_width=self.flange_width.get(),
                flange_thickness=self.flange_thickness.get(),
                web_thickness=self.web_thickness.get(),
                x=i*self.girder_spacing.get()
            )
            for i in range(self.num_girders.get())
        ]
        for g in girders:
            g.generate_fea(fea, stations)
        
        
        cfs = [
            CrossFrame(cf_id, sta, "K", g1=girders[gi-1], g2=girders[gi])
            for gi in range(1, len(girders))
            for cf_id, sta in enumerate(crossframes, start=1)
        ]

        for cf in cfs:
            cf.generate_fea(fea)
            
        # Supports
        generate_supports(fea, girders, span_lengths, support_type="pinned")

        # Deck
        deck = Deck(self.deck_thickness.get(), self.overhang.get())
        deck.generate_fea(fea, girders, 0, total_length, crossframes, mesh_size)
        self.last_fea = fea
        # Draw 3D
        draw_3d(fea, self.ax)
        self.canvas.draw()
    

    def run_llm_command(self):
        prompt = self.chat_entry.get().strip()
        if not prompt:
            return
        self.chat_entry.delete(0, "end")

        # show user message

        # call LLM
        state = self.to_llm_dict()
        self.add_chat_message("You", prompt,state)

        if self.last_prompt and self.last_answer:
            context = (
                f"Previous user instruction: {self.last_prompt}\n"
                f"Previous assistant answer: {self.last_answer}\n"
                f"New instruction: {prompt}\n"
                f"Current state: {state}"
            )
        else:
            context = f"Current state: {state}\nInstruction: {prompt}"
            
            
        
        system_prompt = """
        You are an assistant for parametric bridge modeling.
        
        The engineer gives instructions in natural language.
        You always respond with a JSON object.
        
        - All units are in feet. Do NOT convert to meters or any other system.
        
        - If the instruction changes the model, output updates using keys:
          {span_lengths, number_of_girders, girder_spacing, girder_depth, flange_width, flange_thickness,
           deck_thickness, overhang, mesh_size, crossframe_spacing}
        
        - If the instruction is a knowledge query (about Eurocode, AASHTO, analysis results, etc.),
          return a JSON object with a single key:
          {"message": "<your answer here>"}
        
        - If the user explicitly asks about analysis results (e.g. "check deflection", "is the force OK"),
          then use the provided results (e.g. max_deflection, forces, stresses).
          Compare against common code limits (e.g. L/800 for deflection).
          If values exceed the limit, provide corrective suggestions, such as:
            - Increase girder depth
            - Add more girders
            - Reduce span length
            - Adjust cross-frame spacing
          Include these suggestions in the message.
        
        Never return free text outside JSON. Always return valid JSON only.
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", 
                 "content": system_prompt},
                {"role": "user", "content": context}
            ],
            temperature=0
        )
        raw = response.choices[0].message.content
        
        # store last prompt/answer
        self.last_prompt = prompt
        self.last_answer = raw
                
        try:
            update = json.loads(raw)
            if "message" in update:
                # show LLM answer in chat only
                self.add_chat_message("LLM", update["message"])
            else:
                # apply model update
                self.add_chat_message("LLM", raw)
                self.update_from_dict(update)
                self.generate_bridge()
        except Exception as e:
            self.add_chat_message("System", f"⚠️ Could not parse: {e}")
        
        
def draw_3d(fea: FEAModel, ax):
    ax.clear()
    # existing lines + surfaces + nodes …
    for s in fea.supports:
        for nid in s.node_ids:
            n = next(n for n in fea.nodes.values() if n.id == nid)
            ax.scatter([n.x], [n.y], [n.z], color="green", s=50, marker="^")  # green triangles
            
            
    # Draw lines (beams, cross-frames)
    for line in fea.lines:
        n1 = next(n for n in fea.nodes.values() if n.id==line.node_start)
        n2 = next(n for n in fea.nodes.values() if n.id==line.node_end)
        ax.plot([n1.x, n2.x], [n1.y, n2.y], [n1.z, n2.z], "k-")

    # Draw surfaces (deck, webs)
    for surf in fea.surfaces:
        nodes = [next(n for n in fea.nodes.values() if n.id==nid) for nid in [surf.node_1, surf.node_2, surf.node_3, surf.node_4]]
        verts = [[(n.x, n.y, n.z) for n in nodes]]
        ax.add_collection3d(Poly3DCollection(verts, alpha=0.3, facecolor="lightblue"))

    xs, ys, zs = zip(*[(n.x, n.y, n.z) for n in fea.nodes.values()])
    ax.scatter(xs, ys, zs, color="red", s=10)   # s=point size
    set_equal_3d(ax, xs, ys, zs)

    # # Axes labels & view
    # ax.set_xlabel("X (length)")
    # ax.set_ylabel("Y (transverse)")
    # ax.set_zlabel("Z (depth)")
    # ax.view_init(elev=20, azim=-60)
    
    
        # --- cleanup view ---
    ax.set_axis_off()        # hides all axes, ticks, labels
    ax.grid(False)           # no grid
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    ax.set_axis_off()
    ax.margins(0)                # remove margins
    ax.figure.tight_layout()     # tight layout for full fit
    ax.figure.subplots_adjust(left=0, right=1, top=1, bottom=0)  # full bleed
    ax.set_title("FEA Placeholder View (3D)")

def set_equal_3d(ax, X, Y, Z):
    """Force equal aspect ratio in 3D plots."""
    max_range = max(
        max(X)-min(X),
        max(Y)-min(Y),
        max(Z)-min(Z)
    ) / 2.0
    mid_x = (max(X)+min(X)) * 0.5
    mid_y = (max(Y)+min(Y)) * 0.5
    mid_z = (max(Z)+min(Z)) * 0.5
    ax.set_xlim(mid_x - max_range, mid_x + max_range)
    ax.set_ylim(mid_y - max_range, mid_y + max_range)
    ax.set_zlim(mid_z - max_range, mid_z + max_range)
              
    

if __name__ == "__main__":
    root = tk.Tk()
    app = BridgeUI(root)
    root.mainloop()
    
    