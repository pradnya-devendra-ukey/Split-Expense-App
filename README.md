# 🧾 SmartSplit - AI Expense Splitter & Multi-Trip Aggregator

SmartSplit is a full-stack, mobile-first web app that lets you scan restaurant receipts with Google Gemini AI or create bills manually, customize exact item-by-item portions, manage bills paid by **multiple people upfront**, auto-distribute **tax & tip**, organize multi-receipt **trips & groups**, and settle debts in **1 tap via UPI or WhatsApp**.

---

## ⚡ Key Highlights

- 📸 **Gemini AI Vision OCR**: Scan any paper bill to instantly extract line items and prices.
- 📝 **Manual Bill Creator & Item Editor**: Create bills without photos, edit item names/prices, add or delete items dynamically.
- 🍕 **Fractional Item Splitting**: Pick `Full (1/1)`, `1/2 Half`, `1/3 Third`, `1/4 Quarter`, or `/N` shares per product.
- 💳 **Native Multi-Payer Support**: Split bills paid by 2 or more people at the counter.
- 🧾 **Tax, Tip & Service Charge Auto-Distributor**: Choose between **Proportional to items** or **Equal split**.
- 🏖️ **Trips & Groups Multi-Receipt Aggregator**: Combine multiple receipts under a single trip (e.g. "Goa Vacation") with consolidated debt simplification.
- 🌍 **Multi-Currency Support**: Support for `₹ INR`, `$ USD`, `€ EUR`, `£ GBP`, `د.إ AED`, `C$ CAD`, `S$ SGD`, `A$ AUD`, `¥ JPY`, `CHF CHF`.
- 🔑 **6-Character Private Join Codes**: Join rooms via simple codes like `CAFE92` or shareable URL links.
- 💬 **1-Tap WhatsApp Summary & PDF Export**: Formatted message generator for WhatsApp, formatted text copy, and print-ready receipts.
- 🧠 **Greedy Debt Simplification**: Calculates Net Balances and minimizes total transactions (Splitwise-style).
- ⚡ **1-Tap UPI Settlement**: Deep links directly to GPay, PhonePe, Paytm, and displays QR codes.
- 📂 **Expense Memory**: Persistent database tracking of all receipts, shares, and payment settlements.

---

## 📖 Full Documentation

For the complete technical guide, architecture breakdown, ER diagrams, and API specifications, see:
👉 **[PROJECT_DOCUMENTATION.md](file:///d:/projects/Split-Expense-App/PROJECT_DOCUMENTATION.md)**

---

## 🚀 Quick Start

1. **Install requirements**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure `.env`**:
   ```env
   GEMINI_API_KEY="your-gemini-api-key"
   DATABASE_URL="sqlite:///./expense.db"
   ```

3. **Run the server**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Open in browser**:
   Navigate to [http://localhost:8000](http://localhost:8000) or Swagger UI at [http://localhost:8000/docs](http://localhost:8000/docs).
