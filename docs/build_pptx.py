"""Build docs/BioPay_Presentation.pptx. Needs: pip install python-pptx pillow (not in requirements.txt)."""
from pathlib import Path
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

A = Path(__file__).parent / "assets"
BG, PANEL, FG, MUT, ACC, WARN = (RGBColor.from_string(c) for c in ("0A101C", "141F33", "E8EDF6", "94A1B8", "2DD4BF", "F2B84B"))
prs = Presentation(); prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

def slide(title=None, notes=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid(); s.background.fill.fore_color.rgb = BG
    if title:
        t = s.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12), Inches(0.8)).text_frame
        r = t.paragraphs[0].add_run(); r.text = title; r.font.size = Pt(32); r.font.bold = True; r.font.color.rgb = FG; r.font.name = "Calibri"
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(1.15), Inches(1.1), Emu(38000)); bar.fill.solid(); bar.fill.fore_color.rgb = ACC; bar.line.fill.background()
    foot = s.shapes.add_textbox(Inches(0.6), Inches(7.05), Inches(12), Inches(0.3)).text_frame
    r = foot.paragraphs[0].add_run(); r.text = "BioPay  |  SIMULATED PAYMENT — NO REAL MONEY  |  college IoT project"; r.font.size = Pt(10); r.font.color.rgb = MUT
    if notes: s.notes_slide.notes_text_frame.text = notes
    return s

def bullets(s, items, x=0.6, y=1.5, w=12.0, h=5.3, size=20, color=FG):
    tf = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame; tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph(); p.space_after = Pt(10)
        r = p.add_run(); r.text = "•  " + it; r.font.size = Pt(size); r.font.color.rgb = color; r.font.name = "Calibri"

def pic(s, name, x, y, w, h):
    iw, ih = Image.open(A / name).size; k = min(w / iw, h / ih)
    pw, ph = iw * k, ih * k
    s.shapes.add_picture(str(A / name), Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2), Inches(pw), Inches(ph))

def tag(s, text, x=0.6, y=6.55, color=WARN):
    tf = s.shapes.add_textbox(Inches(x), Inches(y), Inches(12), Inches(0.4)).text_frame
    r = tf.paragraphs[0].add_run(); r.text = text; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = color

# 1 title
s = slide(notes="Introduce the project: simulated BioCoins, no real money; software complete, hardware pending.")
pic(s, "screen-landing-hero.jpg", 6.6, 1.2, 6.4, 3.6)
tf = s.shapes.add_textbox(Inches(0.6), Inches(1.7), Inches(6.2), Inches(3)).text_frame; tf.word_wrap = True
r = tf.paragraphs[0].add_run(); r.text = "BioPay"; r.font.size = Pt(66); r.font.bold = True; r.font.color.rgb = ACC
p = tf.add_paragraph(); r = p.add_run(); r.text = "Phone-free biometric checkout demonstration"; r.font.size = Pt(26); r.font.color.rgb = FG
p = tf.add_paragraph(); r = p.add_run(); r.text = "College IoT project  •  Simulated BioCoins"; r.font.size = Pt(16); r.font.color.rgb = MUT
tag(s, "Submitted by: ______________   Guide: ______________", y=5.6, color=MUT)
# 2
s = slide("Problem statement"); bullets(s, ["Phone-based payment fails when the phone is lost, flat or offline.", "Fingerprint checkout removes the phone, but a careless design can:", "    charge twice after a network failure", "    let a merchant charge the wrong person", "    store fingerprints on a server", "    keep working after consent is withdrawn", "Goal: a fingerprint-checkout flow that avoids all four."])
# 3
s = slide("Project objectives"); bullets(s, ["Atomic transfers; every payment applied at most once.", "Fingerprint templates stay on the sensor; server sees a slot number only.", "Separate customer, merchant and admin views with an audit trail.", "Consent, withdrawal and revocation take effect immediately.", "Verified by automated tests and a repeatable demo.", "Clean interface ready for the real sensor and terminal."])
# 4
s = slide("Proposed solution"); bullets(s, ["Sensor matches the finger and returns only a slot number.", "Terminal creates a payment ID, saves it, then sends the request.", "Server resolves the customer from terminal + slot, locks rows in a fixed order.", "Debit and credit commit together; the result is stored under the payment ID.", "A retry with the same ID returns the stored result: no second charge."])
# 5
s = slide("System architecture"); pic(s, "diagram-architecture.png", 0.6, 1.4, 12.1, 5.0); tag(s, "Dashed = planned hardware (not built or tested yet)")
# 6
s = slide("Technology stack"); bullets(s, ["Frontend: React 19, TypeScript, Vite, Tailwind CSS", "3D: Three.js, React Three Fiber, Drei, GSAP ScrollTrigger", "Backend: Python 3.12, Django 5.2, Django REST Framework", "Database: PostgreSQL (locks, transactions, constraints)", "Testing: Django tests, Playwright, axe-core, native C++ firmware tests", "Firmware (planned): ESP32-S3; payment core already written in portable C++"])
# 7
s = slide("Fingerprint enrollment workflow"); bullets(s, ["1. Customer registers and ticks consent (starting BioCoins recorded as opening balance).", "2. Customer enrolls a fingerprint on a terminal and gives a second consent.", "3. Sensor stores the template locally; server stores terminal, slot, status, consent time.", "4. Customer can withdraw: deletion request, then admin completes revocation.", "5. Software demo uses a clearly labelled mock enrollment instead of a sensor."]); tag(s, "Real sensor enrollment: NOT YET TESTED")
# 8
s = slide("Payment processing workflow"); pic(s, "diagram-payment-sequence.png", 0.9, 1.35, 11.5, 5.2); tag(s, "Dashed arrows = planned hardware steps; API + database part verified by tests", y=6.6)
# 9
s = slide("Backend and database design"); pic(s, "diagram-database.png", 0.6, 1.35, 8.2, 5.4)
bullets(s, ["Wallet balance >= 0 (CHECK)", "Payment ID = UUID primary key", "Two ledger rows per payment, sum 0", "One live enrollment per slot", "Reconciliation: opening + ledger = balance"], x=9.0, y=1.6, w=4.0, size=16)
# 10
s = slide("Website and dashboards"); pic(s, "screen-landing-wallet.jpg", 0.5, 1.4, 4.1, 2.5); pic(s, "screen-customer.jpg", 4.7, 1.4, 4.1, 2.5); pic(s, "screen-simulator.jpg", 8.9, 1.4, 4.1, 2.5)
pic(s, "screen-admin.jpg", 0.5, 4.0, 6.1, 2.8); bullets(s, ["Six-scene scroll-driven 3D landing page", "Customer wallet, history, enrollment, consent", "Merchant dashboard and labelled simulator", "Admin: reconciliation, audit log, revocation"], x=6.9, y=4.1, w=6.0, h=2.7, size=16)
# 11
s = slide("Security, privacy and consent"); bullets(s, ["No fingerprint data on the server; a slot number only has meaning with its terminal.", "Roles decided by the server; merchants see only 'Customer #n'.", "Terminal keys stored as hashes; passwords hashed, 12+ characters, common ones refused.", "CSRF protection; login and registration rate limited.", "Revoked terminal or enrollment blocks new payments immediately.", "Simulator needs the customer's opt-in, enforced under the payment's database lock; development mode only.", "Audit log for sensitive actions."])
# 12
s = slide("Testing and results"); bullets(s, ["Backend (PostgreSQL, incl. concurrency): 105 passed", "Browser tests (Playwright, API mocked): 18 passed", "Real-stack end-to-end (Django + PostgreSQL + Vite): all steps passed", "Firmware core (native): passed;  TypeScript + build: clean;  lint: 0 errors", "Accessibility (axe WCAG 2 A/AA) on the main pages of every role: 0 violations", "No horizontal overflow at 320 – 1920 px on those pages"], size=19)
tag(s, "Not measured: screen-reader session, real GPU frame rate, load testing", color=MUT)
# 13
s = slide("Hardware integration plan"); pic(s, "diagram-hardware-plan.png", 0.7, 1.35, 8.0, 5.2)
bullets(s, ["Needed first: sensor model + interface, ESP32-S3 board, display, input, power", "Then: sensor code, Wi-Fi + HTTPS, flash storage for payment ID", "Server: real-sensor mode + HTTPS"], x=8.9, y=1.6, w=4.2, size=15)
tag(s, "BLOCKED — HARDWARE MODEL AND PINOUT REQUIRED (nothing here is verified)")
# 14
s = slide("Limitations and future scope")
bullets(s, ["Limitations", "    Physical terminal and real sensor not built or tested", "    Terminal API runs only in development mode today", "    Audit log immutable by convention, not by a database rule", "    Tested with tens of users, not at scale"], x=0.6, y=1.5, w=6.0, size=18)
bullets(s, ["Future scope", "    Real sensor + liveness checks", "    HTTPS with device certificates", "    Hardware-backed key storage on the ESP32", "    Refunds, receipts, load testing"], x=7.0, y=1.5, w=6.0, size=18)
# 15
s = slide("Conclusion and demo", notes="Demo: scripts/demo.sh start; follow docs/DEMO_SCRIPT.md.")
bullets(s, ["BioPay software platform is complete and verified; payments are atomic, idempotent and consent-aware.", "Physical fingerprint integration is the remaining step.", "Live demo: register → consent → enroll → pay 60 → resend (no double charge) → decline → admin reconciliation."], y=1.5, h=3, size=20)
pic(s, "screen-simulator-mobile.jpg", 9.6, 4.0, 2.0, 2.9); tag(s, "Start: scripts/demo.sh start  →  http://127.0.0.1:5173/", y=5.2, color=ACC)
prs.save(Path(__file__).parent / "BioPay_Presentation.pptx"); print("slides:", len(prs.slides))
