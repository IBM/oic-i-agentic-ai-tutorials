# Build an agentic accounts-payable system with watsonx Orchestrate and Odoo

![Agentic accounts payable on IBM watsonx Orchestrate and Odoo](images/cover.png)

*Process any accounts-payable document, from GST supplier invoices to employee taxi receipts, with an agentic
flow, decision tables, governed agents and a live ERP.*

By Aditya Krishnan

[Read this guide as a web page](https://claude.ai/artifact/LeZnzxhrq9psD5PNUU1rLC)

## Introduction

Accounts payable (AP) teams still key in most of what lands in their inbox. A mid-sized manufacturer
receives 100 to 200 supplier invoices a day, plus employees' taxi and hotel receipts, signed purchase-order copies
and the delivery challans that arrive with goods. Capture tools read the text, but the checks that decide whether a bill
can be paid stay manual:

- Is the tax charged under the right regime for the place of supply?
- Which withholding tax applies, and at what rate?
- Did the goods actually arrive?
- Is the "new bank account" printed on the invoice genuine?

In this tutorial, you build a system that takes any of those documents from receipt to the right action in the
ERP. It uses [IBM watsonx Orchestrate](https://www.ibm.com/products/watsonx-orchestrate) for document processing,
the process flow, two conversational agents and governance, and [Odoo](https://www.odoo.com) as the ERP of record.

The sample company uses India's GST and TDS as its worked example of local tax rules. The rules live in one
module, `wxo/tools/apcore/india.py`, so you can replace them with another country's rules without changing the
flow, the decision tables or the agents.

### What you'll learn

- How to read and classify several document types with one document processing node and multiple key-value
  schemas.
- How to build a process as an agentic flow with script, prompt, tool, decision-table and branch nodes.
- How to call an ERP from tool nodes with credentials kept in an Orchestrate connection.
- How to give business users a decision table they can change without code.
- How to govern agents with the control plane: guardrails, PII masking, rate limits and a model fallback policy.

### What you'll build

Meridian Specialty Chemicals is a fictional chemicals manufacturer. Its AP team wants to drop any
document into one place and have it handled:

> "Here's Coromandel's invoice, Ananya's taxi receipt from yesterday, and the challan for Narmada's balance two
> tonnes. Book what's clean and tell me what needs me."

When you finish, your system does the following for every document:

1. Reads it and works out what it is: a supplier invoice, an expense receipt, a PO copy, a delivery challan, or
   something it doesn't handle.
2. Runs the checks that apply to that type against live Odoo data.
3. Routes it with a decision table that the AP team owns.
4. Acts in Odoo: posts or holds a vendor bill, approves or holds an expense, books a goods receipt, or blocks a
   duplicate.
5. Explains the decision. Each Odoo record carries the agent's control log, and the workbench highlights the
   fields that failed.

## Architecture

![Architecture: intake channels feed the ap_document_processing_flow in watsonx Orchestrate, which branches by document type and acts on Odoo; a Carbon workbench, two agents and the control plane sit on top.](images/architecture.png)

The solution has five components:

1. **Document flow** (`ap_document_processing_flow`). The process itself, built with the watsonx Orchestrate
   Agent Development Kit (ADK). A document processing node runs OCR and extracts key-value pairs and tables. A
   branch then sends each document type down its own path.
2. **Shared AP engine** (`wxo/tools/apcore`). Standard-library Python for the tax rules, the Odoo client, the
   controls and the booking logic. The tools deploy it to Orchestrate, and the workbench imports the same code,
   so the rules never diverge.
3. **Odoo ERP**. The system of record for vendors, purchase orders, goods receipts, vendor bills and expenses.
   Tools reach it over XML-RPC.
4. **Agents**. The *AP Copilot* serves the finance team and can approve a held bill after confirmation. The
   *Supplier Desk* serves suppliers; it is read-only and answers only for the caller's GSTIN.
5. **Control plane**. Guardrails, PII and IFSC masking, a secrets detector, tool rate limits and a model policy
   that runs Claude Sonnet 4.6 with gpt-oss-120b as the fallback.

A document moves through the system like this:

1. It arrives by upload or email. The workbench stores it in the Orchestrate tenant with
   `POST /v1/orchestrate/upload-to-s3` and starts the flow.
2. The flow reads the document, picks its type and runs that type's nodes. The LLM is used only for judgement:
   the nature of payment for TDS, and the expense category. Every number, GSTIN, limit and ERP match is checked
   in code, so each decision is reproducible.
3. A decision table routes the result, and a tool node writes to Odoo.
4. The workbench polls the flow and shows each node as it completes.

## Prerequisites

Before you start, make sure you have the following:

- An [IBM watsonx Orchestrate](https://www.ibm.com/products/watsonx-orchestrate) instance on IBM Cloud. A trial
  works.
- Python 3.12 and [uv](https://docs.astral.sh/uv/) on your computer.
- Git.
- An email address you can use for a free [Odoo trial](https://www.odoo.com/trial).
- Optional: a Gmail account with 2-Step Verification turned on, if you want email intake.

You don't need to install the watsonx Orchestrate ADK separately. The project installs version 2.18, which this
tutorial was tested with.

## Estimated time

It takes about 60 minutes to complete this tutorial: 25 minutes to set up and deploy, and 35 minutes to run the
scenarios and explore the agents.

## Steps

### Step 1. Get the code and install the tools

In this step, you clone the repository and create a Python environment with the ADK and the workbench
dependencies.

1. Clone the repository:

   ```bash
   git clone https://github.com/adiDaBEzt/agentic-accounts-payable.git
   cd agentic-accounts-payable
   ```

2. Create the virtual environment and install the dependencies:

   ```bash
   uv venv -p 3.12 .venv
   uv pip install -p .venv -r requirements.txt
   ```

3. Check that the ADK is installed:

   ```bash
   .venv/bin/orchestrate --help
   ```

   The command prints the list of `orchestrate` subcommands, including `agents`, `tools`, `connections` and
   `models`.

The repository is organised like this:

| Path | What it contains |
|---|---|
| `wxo/flows/` | The agentic flow, `ap_document_processing_flow.py` |
| `wxo/tools/` | The Python tools and the shared AP engine, `apcore/` |
| `wxo/agents/` | The AP Copilot and Supplier Desk agent definitions |
| `wxo/controls/` | The control-plane policies, as YAML |
| `wxo/deploy.sh` | One script that deploys everything to Orchestrate |
| `app/` | The AP workbench: a FastAPI back end and a Carbon-style front end |
| `scripts/` | Odoo provisioning and the sample-document generator |
| `samples/` | 13 sample documents covering every scenario |

### Step 2. Create an Odoo database

In this step, you create the ERP that the agent checks documents against.

1. Go to [odoo.com/trial](https://www.odoo.com/trial) and start a free trial. Select the **Accounting** app.
2. When Odoo asks for your company details, set the country to **India**, to match the sample company. Odoo then
   installs the fiscal localisation that provides the GST and TDS taxes the agent uses.
3. Note your database URL, for example `https://meridian-ap.odoo.com`. The database name is the part before
   `.odoo.com`, here `meridian-ap`.
4. Create an API key for the agent to sign in with. Click your avatar in the upper right, open your profile or
   preferences, go to the **Account Security** tab and click **New API Key**. Copy the key; Odoo shows it only once.

> **Note:** The tutorial works with any Odoo 18 or later database that has the `l10n_in` localisation. The setup script
> in Step 5 installs Purchase, Inventory, Employees and Expenses for you.

### Step 3. Get your watsonx Orchestrate credentials

In this step, you collect the two values that the ADK and the workbench use to reach your Orchestrate instance.

1. Open watsonx Orchestrate. Click your avatar in the upper right and select **Settings**.
2. Open the **API details** tab.
3. Copy the **Service instance URL**. It looks like
   `https://api.<region>.watson-orchestrate.cloud.ibm.com/instances/<instance-id>`.
4. Click **Generate API key**. IBM Cloud opens its API keys page. Create a key and copy it.

### Step 4. Configure the project

In this step, you put your credentials in a local `.env` file. The file is in `.gitignore`, so your credentials
never reach the repository.

1. Copy the example file:

   ```bash
   cp .env.example .env
   ```

2. Open `.env` and fill in the values from Steps 2 and 3. Leave the Gmail section as it is for now:

   ```ini
   # --- IBM watsonx Orchestrate ---
   WXO_INSTANCE_URL=https://api.<region>.watson-orchestrate.cloud.ibm.com/instances/<instance-id>
   WXO_API_KEY=<your IBM Cloud API key>

   # --- Odoo ERP (XML-RPC) ---
   ODOO_URL=https://meridian-ap.odoo.com
   ODOO_DB=meridian-ap
   ODOO_USERNAME=<the email you sign in to Odoo with>
   ODOO_PASSWORD=<your Odoo API key>
   ```

3. Load the values into your shell, so the next commands can use them:

   ```bash
   set -a; source .env; set +a
   ```

> **Important:** Tool code never contains the Odoo credentials. In Step 8, the deploy script stores them in an
> Orchestrate *connection*, and each tool declares that it needs the connection.

### Step 5. Seed Odoo with the demo company

In this step, you load a small but realistic world into Odoo: vendors, purchase orders, goods receipts,
employees and expense policy limits. Every sample document is generated from the same data, so the documents
and the ERP always agree.

1. Run the setup script:

   ```bash
   .venv/bin/python scripts/setup_odoo.py
   ```

   The script takes a few minutes the first time, because it installs Odoo apps. You see a section for each
   stage:

   ```output
   Odoo: https://meridian-ap.odoo.com / meridian-ap

   ▸ Installing Purchase + Inventory
     purchase: installed
     stock: installed

   ▸ Activating GST & TDS taxes
   ▸ Configuring buyer company
   ▸ Vendor master
   ▸ Products
   ▸ Purchase orders & receipts
   ▸ Installing Employees + Expenses
   ▸ Employees & corporate cards
   ▸ Expense categories

   Done.
   ```

2. Check the result in Odoo. Open **Purchase**: you see five confirmed purchase orders, one per vendor, such as
   Sahyadri Drums & Containers and Narmada Petrochem Industries. Open **Employees**: you see Vikram Desai,
   Ananya Rao, Rahul Mehta and Priya Nair.

> **Tip:** The script is idempotent. If a step fails, for example because Odoo is still installing an app, run
> it again. It updates what exists and creates only what is missing.

What the script sets up, and why it matters later:

- Five vendors, each with a verified bank account and tags for its TDS section and e-invoicing status.
- Five purchase orders with goods receipts. The Narmada order is deliberately short by 2 tonnes, so you can see
  a 3-way-match exception.
- Four employees, three with corporate cards, and five expense categories with policy limits.

### Step 6. Connect the ADK to watsonx Orchestrate

In this step, you register your Orchestrate instance with the ADK and check that the models the solution uses
are available in your tenant.

1. Add your instance as an ADK environment and activate it:

   ```bash
   .venv/bin/orchestrate env add -n ap-demo -u "$WXO_INSTANCE_URL" --type ibm_iam
   .venv/bin/orchestrate env activate ap-demo --api-key "$WXO_API_KEY"
   ```

2. Check that Claude Sonnet 4.6 and gpt-oss-120b are available:

   ```bash
   .venv/bin/orchestrate models list | grep -E "claude-sonnet-4-6|gpt-oss-120b"
   ```

   You should see both models in the output:

   ```output
   bedrock/us.anthropic.claude-sonnet-4-6
   groq/openai/gpt-oss-120b
   ```

> **Note:** If your tenant doesn't list one of the models, edit the `models policy add` line in `wxo/deploy.sh`
> and replace it with a model from your list. The agents and the flow refer only to the policy name,
> `ap_claude_fallback`, so nothing else changes.

### Step 7. Explore the document flow

In this step, you read how the flow is built before you deploy it. Open `wxo/flows/ap_document_processing_flow.py`
alongside this section.

1. **Read and classify in one node.** The document processing node gets all four schemas (GST tax invoice,
   expense receipt, purchase order and delivery challan) and no forced schema. It extracts the fields and records
   the matching schema in `metadata.pages_metadata[0].document_type`:

   ```python
   read = aflow.docproc(
       name="read_document",
       task="text_extraction",
       output_format=DocProcOutputFormat.object,
       enable_hw=True,
       kvp_schemas=[GST_INVOICE_SCHEMA, RECEIPT_SCHEMA, PO_SCHEMA, CHALLAN_SCHEMA],
       kvp_enable_text_hints=True,
   )
   ```

   The `document_description` on each schema drives the choice, so say what each type is *not*. A taxi receipt
   titled "Tax invoice" was first read as a supplier invoice. Describing receipts as coming from "a cab operator,
   hotel, restaurant or merchant … even when titled 'tax invoice'" fixed it.

2. **Branch on the type.** A script node, `identify_document`, maps the detected schema to a type and
   normalises the fields. A branch then routes each type to its own lane:

   ```python
   by_type = aflow.branch(name="document_type",
                          evaluator='flow["identify_document"].output.doc_type')
   (by_type.case("supplier_invoice", checks).case("expense_receipt", category)
    .case("purchase_order", verify).case("delivery_challan", receive).case("other", END))
   ```

3. **Keep the checks deterministic.** In the invoice lane, a script node checks the GSTIN check digit, the
   CGST and SGST versus IGST regime, the tax slab and the arithmetic. A prompt node classifies the nature of
   payment for TDS. Then the `ap_erp_controls` tool node checks the vendor master, bank account, duplicates, IRN,
   PO price and received quantity against live Odoo data, and computes TDS.

4. **Put the policy in a decision table.** The table reads the tool's counts and sets the route. The first
   matching rule wins:

   ```python
   rule("erp_controls", ("duplicates", DecisionsCondition().greater_than(0)), "blocked", "Duplicate invoice")
   rule("erp_controls", ("exceptions", DecisionsCondition().greater_than(0)), "exception", "")
   rule("erp_controls", ("invoice_total", DecisionsCondition().greater_than(2_500_000)), "exception",
        "Above ₹25 lakh touchless limit")
   ```

   After you deploy, the AP team can change a threshold such as the ₹25 lakh touchless limit in the flow editor,
   without touching code.

   ![The AP routing policy decision table in the watsonx Orchestrate flow builder.](images/wxo-decision-table.png)

5. **Act through tool nodes.** A second branch sends `touchless` to the `post_bill` tool, `exception` to
   `hold_bill`, and `blocked` to the end. The expense lane has the same shape, with its own prompt node, tool
   and decision table.

### Step 8. Deploy the solution to watsonx Orchestrate

In this step, you deploy the connection, tools, flow, model policy, agents and controls with one script.

1. Run the deploy script from the project root:

   ```bash
   ORCH=.venv/bin/orchestrate ./wxo/deploy.sh
   ```

   The script prints a line for each stage, followed by the ADK's messages for each item it imports:

   ```output
   ▸ Connection: odoo_erp (key-value, team credentials)
   ▸ Tools (Odoo via connection; the flow's process tools first)
   ▸ Flow: ap_document_processing_flow
   ▸ Model policy: Claude Sonnet 4.6 primary, gpt-oss-120b fallback
   ▸ Agents
   ▸ Controls (control plane)
   Done.
   ```

   The order matters. The flow's tools are imported before the flow, because the flow reads their schemas when
   it is imported.

2. Check the deployment in watsonx Orchestrate. Open the flow builder and find `ap_document_processing_flow` in
   your agentic workflows. You see one lane per document type:

   ![The complete ap_document_processing_flow in the watsonx Orchestrate flow builder, with one lane per document type.](images/wxo-flow-canvas.png)

3. Open the agent list. You see **AP Copilot** and **Supplier Desk**.

Each tool declares the connection it needs, so the Odoo credentials stay out of the code:

```python
@tool(name="ap_erp_controls", permission=ToolPermission.READ_ONLY, expected_credentials=ODOO_CREDENTIALS)
def ap_erp_controls(invoice: Invoice, payment_nature: PaymentNature, data: dict | None = None) -> ControlOutcome:
```

> **Note:** The parameters use typed Pydantic models rather than `dict`. The tool also accepts an unused `data`
> argument, because the flow runtime passes the previous node's output under that name.

### Step 9. Start the AP workbench

In this step, you start the workbench that the AP team uses to drop documents in and review the results.

1. Start the server:

   ```bash
   .venv/bin/uvicorn app.main:app --port 8090
   ```

2. Open [http://localhost:8090](http://localhost:8090) in your browser.

3. Check the status indicators in the header. **watsonx Orchestrate** and **Odoo ERP** show a green dot when the
   workbench can reach them. **Gmail** stays grey until you complete Step 15.

   ![The AP workbench overview: touchless rate, value processed, open exceptions, duplicates blocked, TDS and cycle time.](images/ui-overview.png)

> **Tip:** The reset icon in the header removes the bills and expenses the agent created and reverses the goods it
> received. Use it whenever you want to run the scenarios again from a clean state.

### Step 10. Process supplier invoices

In this step, you run the six supplier-invoice samples and see each possible outcome: posted without a human
touch, held for review, and blocked.

1. Click **Process document**. You can drag any PDF or image onto the dialog, or pick a sample scenario.

   ![The Process a document dialog with sample scenarios grouped by document type.](images/ui-process-dialog.png)

2. Process the samples in this order. Each takes about 30 to 40 seconds. Check that you get the expected outcome:

   | Sample | What it tests | Expected outcome |
   |---|---|---|
   | `01_sahyadri…` | Clean invoice with a matching PO and goods receipt | Posted touchless |
   | `02_kaveri…` | Services invoice that needs TDS | Posted touchless, TDS ₹41,200 |
   | `03_narmada…` | 10 tonnes billed, 8 received | Held: GRN shortage |
   | `04_coromandel…` | CGST and SGST on an inter-state supply, and a new bank account | Held: wrong GST regime, bank account changed |
   | `05_konkan…` | Price above the PO, and no e-invoice IRN | Held: price above PO, IRN missing |
   | `06_…_scan.png` | A phone scan of invoice 01 | Blocked: duplicate |

3. Open the Kaveri invoice. The prompt node classified the HAZOP study as professional fees, and the tool
   applied TDS under section 393(1) Sl.6(iii)(b) of the Income-tax Act 2025 (formerly 194J) at 10%, ₹41,200. The
   tax is added to the Odoo bill as a withholding tax.

   ![The Kaveri invoice posted touchless with TDS of ₹41,200 to be withheld at payment.](images/ui-invoice-tds.png)

4. Open the **ERP & audit trail** tab. It lists every flow node and how long it took.

   ![Processing trail for the Kaveri invoice, listing each flow node and its duration.](images/ui-flow-trail.png)

5. Open the Coromandel invoice. Two checks failed, and the failing fields are outlined in red on the document.
   The bill is a draft in Odoo with a review task assigned.

   ![The Coromandel invoice held for review, with red boxes on the bank details and tax lines.](images/ui-invoice-exception.png)

6. Open the Narmada invoice and select the **3-way match** tab. It shows where the variance comes from: 10
   tonnes ordered, 8 received, 10 billed.

   ![3-way match for the Narmada invoice: ordered 10, received 8, quantity variance.](images/ui-three-way-match.png)

> **Note:** Process `06` after `01`. It is a duplicate only once invoice 01 exists in Odoo.

### Step 11. Process receipts, PO copies and challans

In this step, you run the other document types through the same flow. The flow recognises each type by itself;
you don't tell it what you are uploading.

1. Process the remaining samples in this order and check the outcomes:

   | Sample | What it tests | Expected outcome |
   |---|---|---|
   | `07_receipt_cityride_taxi` | Taxi on Ananya's corporate card, within policy | Approved |
   | `08_receipt_hotel_sabarmati` | Hotel above the ₹6,000 a night limit, paid personally | Held for the manager |
   | `09_receipt_coastal_kitchen` | Client dinner within the meals limit | Approved; GST credit blocked under s.17(5) |
   | `10_…_photo.jpg` | The taxi receipt again, submitted by Rahul | Blocked: duplicate, and not his card |
   | `11_po_copy…` | Supplier-signed copy of MSC-PO-26-0161 | Verified against the Odoo PO |
   | `12_challan_narmada…` | Narmada's missing 2 tonnes arrive | Goods received; held Narmada bill flagged for release |
   | `13_letter…` | A price-revision letter | Unsupported; nothing changes in Odoo |

2. Open the hotel receipt. The expense-policy checks show why it needs the manager.

   ![The hotel receipt held for the manager, above the per-night limit.](images/ui-expense-hotel.png)

3. Open the duplicate taxi receipt. Two checks failed: it is a duplicate, and the card on it belongs to another
   employee.

   ![A re-submitted taxi receipt blocked as a duplicate, with the card-owner check failing.](images/ui-expense-duplicate.png)

4. Open the delivery challan. The agent booked the goods receipt in Odoo and left a note on the held Narmada bill:
   the shortage is resolved, so AP can approve it as invoiced.

   ![The delivery challan processed: goods receipt validated and the held bill flagged for release.](images/ui-challan.png)

5. Open **Documents**. You see all 13 documents, their types and their outcomes.

   ![The Documents list showing every document type and its outcome in Odoo.](images/ui-documents.png)

> **Note:** Process `10` after `07`, and `12` after `03`. Each depends on the earlier document being in Odoo.

### Step 12. Review the results in Odoo

In this step, you open the records the agent created. Each one carries the agent's control log as a note, with
failed checks first.

1. In Odoo, open **Accounting > Vendors > Bills** and open a posted bill, such as Kaveri's. You see the GST and
   TDS taxes on each line and the agent's control log in the chatter.

   ![A vendor bill in Odoo posted touchless with IGST and a 10% TDS withholding tax, with the agent's control log in the chatter.](images/odoo-posted-bill-tds.png)

2. Open a draft bill, such as Coromandel's. The review task names the exceptions, and the note lists each check
   with its detail.

   ![A draft bill in Odoo with the AP exception review task and the agent's control log.](images/odoo-held-bill.png)

3. Open **Expenses**. Corporate-card spend is approved and settled. Reimbursable spend shows as approved once
   the manager signs off.

   ![Odoo expenses created by the agent for three employees.](images/odoo-expenses.png)

4. Open **Inventory** and find the receipt booked from the challan. The agent's note records the four receiving
   checks.

   ![The goods receipt in Odoo with the agent's receiving checks.](images/odoo-goods-receipt.png)

> **Note:** If you post chatter notes over XML-RPC in your own code, pass `body_is_html=True` to `message_post`.
> Without it, Odoo escapes the HTML and the chatter shows raw tags.

### Step 13. Talk to the agents

In this step, you use the two agents. Both use the same Odoo tools, with different permissions.

1. In the workbench, open **Assistants** and select **AP Copilot**. Ask:

   ```text
   Which expense claims are waiting for manager approval, and what is on hold in AP?
   ```

   The Copilot calls the `expense_claims` and `ap_exception_worklist` tools and answers with a table and next
   steps.

   ![The AP Copilot listing held bills with amounts, exceptions and links to Odoo.](images/ui-copilot.png)

2. Ask the Copilot to approve the Coromandel bill. It refuses, because the bank account changed. It approves a
   held bill only after you confirm, and never one with a changed bank account or a duplicate.

3. Select **Supplier Desk** and ask as a supplier:

   ```text
   What is the status of invoice KPA/26-27/073? Our GSTIN is 29AAQFK2209M1ZU
   ```

   It answers with the status, the TDS withheld and the expected payment date. It answers only for the GSTIN that
   owns the invoice.

   ![The Supplier Desk answering a supplier's status question.](images/ui-supplier-status.png)

4. Open the AP Copilot in the watsonx Orchestrate agent builder. The **Model** field shows `ap_claude_fallback`,
   the model policy from Step 8. It runs Claude Sonnet 4.6 and falls back to gpt-oss-120b if Claude is
   throttled or returns a server error. The flow's two prompt nodes use the same policy.

   ![The AP Copilot in the watsonx Orchestrate agent builder, answering in the preview chat.](images/wxo-agent-builder.png)

### Step 14. Govern the agents with the control plane

In this step, you see the controls that apply to every agent call, whatever the prompt says.

1. Open `wxo/controls/supplier_content_guardrails.yaml`. It screens the supplier channel before the agent sees a
   message:

   ```yaml
   spec_version: v1
   kind: control
   control:
     artifact_name: Content Guardrails
     name: supplier_content_guardrails
     hooks: [agent_pre_invoke]
     agent_names: [supplier_desk_agent]
     config:
       enabled: {jailbreak: true, hap: true, harm: true}
       block_message: I can only help with invoice and payment status for your company.
   ```

   The deploy script imported this file and the five others in `wxo/controls/`. You can see them on the
   **Controls** page in watsonx Orchestrate:

   ![The Supplier Desk controls on the watsonx Orchestrate Controls page.](images/wxo-controls.png)

2. In the workbench, open **Governance**. It reads the controls from your tenant and shows where each runs: on
   input, on tool calls, on output, or at the model.

   ![The workbench Governance page showing the active controls and where each runs.](images/ui-governance.png)

3. Click **Try a jailbreak on Supplier Desk**. The guardrail blocks the message before the agent runs, and the
   chat marks the reply **Blocked by control**.

   ![A jailbreak attempt on the Supplier Desk blocked by the content guardrail.](images/ui-guardrail-blocked.png)

> **Note:** The guardrail screens the whole conversation. After a thread contains a jailbreak attempt, later
> messages in that thread are blocked too, so start a new conversation.

### Step 15 (optional). Connect a Gmail AP inbox

In this step, you let suppliers and employees email documents to an AP mailbox.

1. In the Gmail account, make sure 2-Step Verification is on, then create an
   [app password](https://myaccount.google.com/apppasswords).
2. Add the account to `.env`:

   ```ini
   GMAIL_USER=<your AP mailbox>@gmail.com
   GMAIL_APP_PASSWORD=<the 16-character app password>
   GMAIL_POLL_SECONDS=0
   VENDOR_EMAIL_OVERRIDE=<your own address, so no real vendor is emailed>
   ```

3. Restart the workbench. The **Gmail** indicator turns green.
4. Email one of the sample documents to the mailbox as an attachment, then click **Check AP inbox** on the
   Documents page. The document is processed like an upload, and the sender gets an acknowledgement with the
   outcome.

> **Tip:** Set `GMAIL_POLL_SECONDS` to a number such as `60` to check the inbox automatically.

## Troubleshooting

<details>
<summary>The Odoo indicator stays red</summary>

Check `ODOO_URL`, `ODOO_DB` and `ODOO_USERNAME` in `.env`, and that `ODOO_PASSWORD` holds a current API key.
Odoo trial databases expire; if yours has, create a new one and run Step 5 again.
</details>

<details>
<summary>The ADK says the token is missing or expired</summary>

Activate the environment again with `.venv/bin/orchestrate env activate ap-demo --api-key "$WXO_API_KEY"`. If
you work with more than one Orchestrate instance, check that `ap-demo` is the active one before you deploy.
</details>

<details>
<summary>The flow import fails with a schema error</summary>

Run the whole deploy script, not just the flow import. The flow reads its tools' schemas at import time, so the
tools in `ap_process_tools.py` must be imported first.
</details>

<details>
<summary>A document is classified as the wrong type</summary>

Make the `document_description` of each schema in the flow say what the type is *not*, then redeploy. The
document processing node picks the schema whose description fits best.
</details>

<details>
<summary>The AP Copilot answers "I have encountered an error" to every message</summary>

Keep the document flow out of the agent's tool list. With Claude Sonnet 4.6 on Bedrock, an agent that lists the
flow as a tool fails on every message. Documents reach the flow through the workbench and the mailbox instead.
</details>

## Lessons from building it

- **The detected type is in the metadata.** With several key-value schemas and no forced schema, document
  processing reports the match in `metadata.pages_metadata[0].document_type`.
- **Qualify decision-table variables.** Conditions take `flow["node"].output.field`. Actions write to an existing
  variable such as `flow.output.route`, and the branch evaluates that same variable.
- **Map every flow output explicitly.** If a branch doesn't set an output, the runtime tries to map it
  automatically, and that can fail. Give each output an explicit map with a default value.
- **Use a non-zero temperature for near-greedy output.** A prompt node's temperature of `0` is dropped as falsy.
  Use `0.01`.
- **Model fallback is a model policy.** Create it with `orchestrate models policy add`. Agents reference it as
  `virtual-policy/<name>`, and prompt nodes accept the same name as their `llm`.

## Summary

You built an accounts-payable system that recognises five kinds of document, runs the statutory and fraud checks that
usually stay manual, and acts in Odoo through one auditable flow. Two agents handle the conversations with the AP
team and suppliers, and the control plane governs them without changing their prompts. In our runs, a document
went from upload to an Odoo decision in about 30 to 40 seconds.

## Next steps

- **Connect another ERP.** Replace the Odoo client in `wxo/tools/apcore/odoo.py` with SAP S/4HANA OData calls.
  The flow, decision tables and agents stay the same.
- **Add document types.** Add a schema to the document processing node and a lane to the branch. Credit notes
  and debit notes are natural next steps.
- **Put a person in the flow.** Route exceptions to a user-activity node, so approvals happen in Orchestrate
  chat.
- **Propose payment runs.** Add a scheduled flow that proposes the payment batch, with TDS already withheld on
  each bill.

The complete source, sample documents and Odoo provisioning script are in the
[GitHub repository](https://github.com/adiDaBEzt/agentic-accounts-payable).

To learn more, see the [watsonx Orchestrate ADK documentation](https://developer.watson-orchestrate.ibm.com/).
