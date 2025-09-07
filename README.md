# RFEM 6 Bridge Demo with LLM Assistant

This demo showcases a **parametric bridge modeling tool** integrated with the **RFEM 6 API** and an **LLM assistant** (via OpenAI).  
The vision: structural engineers interact with models through **natural language** — modifying parameters, checking results, and validating against engineering codes (Eurocode, AASHTO, etc.).

---

## ✨ Features
- Parametric bridge generation (spans, girders, deck, cross-frames, supports).
- Automatic generation of FEA objects (nodes, lines, surfaces).
- Interactive 3D visualization (matplotlib + Tkinter).
-  **RFEM 6 API integration** for exporting and running real analysis.
- Natural language assistant (OpenAI) to:
  - Change parameters (e.g., “Increase girder spacing by 2 ft”).
  - Check design ratios (e.g., span/depth according to Eurocode).
  - Reason about analysis results (e.g., deflection limits).

---

## ⚙️ Installation

1. **Clone the repo**
   ```bash
   git clone https://github.com/halilujah/rfem-bridge-demo.git
   cd rfem-bridge-demo

2. **Create a virtual environment (recommended)**

python -m venv .venv
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\activate      # Windows

3. **Install dependencies**

pip install -r requirements.txt

4. **Edit config.json and paste your keys**

{
  "OPENAI_API_KEY": "your_openai_api_key_here",
  "RFEM_API_KEY": "your_rfem_api_key_here"
}

5. **Running the Demo**
python main.py


📺 Demo Video

For a full walkthrough of features (parametric modeling, RFEM export, and chat with the LLM assistant), watch the demo video here:

👉 [**Watch the Demo Video**](https://youtu.be/8FWbxS97OHU)