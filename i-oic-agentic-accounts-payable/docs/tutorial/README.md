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

### What you'll learn

- How to read and classify several document types with one document processing node and multiple key-value
  schemas.
- How to build a process as an agentic flow with script, prompt, tool, decision-table and branch nodes.
- How to call an ERP from tool nodes with credentials kept in an Orchestrate connection.
- How to give business users a decision table they can change without code.
- How to govern agents with the control plane: guardrails, PII masking, rate limits and a model fallback policy.

### Usecase overview

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

The Meridian Specialty Chemicals uses India's GST and TDS as its worked example of local tax rules. The rules live
in one module, `wxo/tools/apcore/india.py`, so you can replace them with another country's rules without changing
the flow, the decision tables or the agents.

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

This section lists the implementation steps to complete the tutorial:

1. Lab setup
2. Create an Odoo database
3. Get your watsonx Orchestrate credentials
4. Configure the project
5. Seed Odoo with the demo company
6. Connect the ADK to watsonx Orchestrate
7. Build the document flow
8. Deploy the solution to watsonx Orchestrate
9. Start the AP workbench
10. Process supplier invoices
11. Process receipts, PO copies and challans
12. Review the results in Odoo
13. Talk to the agents
14. Govern the agents with the control plane
15. Connect a Gmail AP inbox (optional)

### Step 1. Lab setup

In this step, you clone the repository and create a Python environment with the ADK and the workbench
dependencies.

1. Clone the repository:

   ```bash
   git clone https://github.com/IBM/oic-i-agentic-ai-tutorials.git
   cd oic-i-agentic-ai-tutorials/i-oic-agentic-accounts-payable
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
| `wxo/flows/` | The finished agentic flow, `ap_document_processing_flow.py`, and the starter you complete in Step 7, `starter/ap_document_processing_flow.py` |
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

### Step 7. Build the document flow

In this step, you read how the flow works and complete it before you deploy it. Open the starter file,
[`wxo/flows/starter/ap_document_processing_flow.py`](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agentic-accounts-payable/wxo/flows/starter/ap_document_processing_flow.py).
It contains the whole flow except three parts, which you add in Tasks 1 to 3 below. Each missing part is a
`todo(...)` line. If you get stuck, compare your code with the finished flow in
[`wxo/flows/ap_document_processing_flow.py`](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agentic-accounts-payable/wxo/flows/ap_document_processing_flow.py).

#### How the flow is organised

Every document starts with the same two nodes, which read it and work out its type. A branch then sends it down
the lane for that type:

| Document type | Nodes in its lane | Result in Odoo |
|---|---|---|
| Supplier invoice | `statutory_checks` → `classify_payment` → `erp_controls` → `route_invoice` | Bill posted, held for review, or blocked |
| Expense receipt | `classify_expense` → `expense_controls` → `route_expense` | Expense approved, held for the manager, or blocked |
| Purchase-order copy | `verify_po` | PO checked and the result logged on it |
| Delivery challan | `receive_goods` | Goods receipt booked |
| Anything else | None | Nothing; left for a person |

The file builds each lane first and connects them at the end, so this section follows the file from top to
bottom.

#### Read and classify the document

The first node, `read_document`, is a document processing node. It runs OCR and extracts key-value pairs and
tables. It gets all four schemas (GST tax invoice, expense receipt, purchase order and delivery challan) and no
forced schema, so it also works out which type of document it has, and records the matching schema in
`metadata.pages_metadata[0].document_type`:

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

The `document_description` on each schema decides the match, so make each description say what the type is
*not*. The taxi receipt
[`07_receipt_cityride_taxi.pdf`](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agentic-accounts-payable/samples/07_receipt_cityride_taxi.pdf) is titled "Tax invoice" and was first
read as a supplier invoice. Describing receipts as coming from "a cab operator, hotel, restaurant or merchant …
even when titled 'tax invoice'" fixed it.

The second node, `identify_document`, is a script node. It maps the detected schema to a document type, such as
`supplier_invoice`, using the `DOC_TYPES` table at the top of the file. It also normalises the extracted fields:
amounts become numbers, dates become ISO dates and GSTINs lose their spaces.

#### Check the invoice in code

The invoice lane starts with `statutory_checks`, a script node that runs every check that needs no ERP data. For a
sample such as [`01_sahyadri_SDC-26-27-0418.pdf`](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agentic-accounts-payable/samples/01_sahyadri_SDC-26-27-0418.pdf), it checks that
the mandatory particulars are present, that the GSTINs pass their check-digit validation, that the invoice charges
CGST and SGST or IGST to match the place of supply, that the GST rate is a notified slab, and that the lines and
totals add up. Each check gets a code, such as `GST-03`, which the workbench shows when the check fails.

The checks run in a script node because they need only the document. Script nodes can't import project modules,
so the checks are written in the flow file itself. The shared AP engine has the same rules in Python, in
[`wxo/tools/apcore/controls.py`](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agentic-accounts-payable/wxo/tools/apcore/controls.py).

#### Task 1. Add the TDS prompt node

The TDS rate depends on what is being paid for, such as goods, professional fees or contract work. That is a
judgement, so a prompt node asks the model. Replace the line `classify = todo(...)` with this code:

```python
classify = aflow.prompt(
    name="classify_payment",
    display_name="Classify nature of payment (TDS)",
    description="Classifies what is being paid for, which drives the TDS section.",
    system_prompt=TDS_SYSTEM_PROMPT,
    user_prompt="Supplier: {supplier_name}\nLine items:\n{lines_text}",
    llm=LLM,
    llm_parameters=PromptLLMParameters(temperature=0.01),  # 0 is dropped by the ADK; near-greedy for repeatability
    input_schema=ClassifierInput,
    output_schema=PaymentNature,
)
classify.map_input("supplier_name", 'flow["statutory_checks"].output.supplier_name')
classify.map_input("lines_text", 'flow["statutory_checks"].output.lines_text')
```

The node sends the supplier name and line items to the model, with the instructions in `TDS_SYSTEM_PROMPT` at the
top of the file. It returns a `PaymentNature`: the nature of payment, a confidence score and a one-line reason.
The two `map_input` lines take the inputs from the `statutory_checks` node. `LLM` is the `ap_claude_fallback`
model policy that you deploy in Step 8.

#### Check the invoice against Odoo

Next, the `erp_controls` tool node calls the `ap_erp_controls` tool in
[`wxo/tools/ap_process_tools.py`](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agentic-accounts-payable/wxo/tools/ap_process_tools.py) with the invoice and the nature of payment:

```python
erp = aflow.tool("ap_erp_controls", name="erp_controls", display_name="ERP controls (Odoo)",
                 error_handler_config=NodeErrorHandlerConfig(error_message="ERP controls failed.", max_retries=1,
                                                             retry_interval=2000))
erp.map_input("invoice", 'flow["statutory_checks"].output')
erp.map_input("payment_nature", 'flow["classify_payment"].output')
```

The tool checks the vendor master, the buyer GSTIN, duplicates, the remittance bank account, the e-invoice IRN,
the PO price and the received quantity (the 3-way match) against live Odoo data. It then works out the TDS
section and rate from the nature of payment, using the rules in
[`wxo/tools/apcore/india.py`](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agentic-accounts-payable/wxo/tools/apcore/india.py). It returns the number of duplicates and failed
controls and the invoice total, which the routing policy uses. If the tool fails, the node retries once.

#### Task 2. Add the routing policy

The AP team owns the rules that decide whether an invoice is posted, held or blocked, so they live in a decision
table that the team can edit later without code. Replace the line `decide = todo(...)` with this code:

```python
decide = aflow.decisions(
    name="route_invoice",
    display_name="AP routing policy",
    description="First matching rule wins: duplicates are blocked, any failed control goes to review, and "
                "clean invoices above the touchless limit need a person's sign-off.",
    rules=[
        rule("erp_controls", ("duplicates", DecisionsCondition().greater_than(0)), "blocked", "Duplicate invoice"),
        rule("erp_controls", ("exceptions", DecisionsCondition().greater_than(0)), "exception", ""),
        rule("erp_controls", ("invoice_total", DecisionsCondition().greater_than(TOUCHLESS_LIMIT_INR)), "exception",
             "Above ₹25 lakh touchless limit"),
    ],
    default_actions={"flow.output.route": "touchless", "flow.output.route_reason": ""},
)
```

The rules are checked in order, and the first match wins. Duplicates are blocked, invoices with a failed control
go to review, and invoices above ₹25 lakh need a person's sign-off. Everything else is posted without a human
touch. The `rule()` helper, defined earlier in the file, writes the result to `flow.output.route`. After you
deploy, the table looks like this in the flow editor:

![The AP routing policy decision table in the watsonx Orchestrate flow builder.](images/wxo-decision-table.png)

#### Act on the invoice in Odoo

A second branch, `route`, reads `flow.output.route` and calls the matching tool:

```python
route = aflow.branch(name="route", display_name="Route invoice", evaluator="flow.output.route")
route.case("touchless", post).case("exception", hold).case("blocked", END)
```

`post_bill` creates and posts the vendor bill in Odoo, with the GST and TDS taxes on each line. `hold_bill` creates
a draft bill with a review task that lists the failed checks. A blocked duplicate, such as
[`06_sahyadri_SDC-26-27-0418_resubmitted_scan.png`](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agentic-accounts-payable/samples/06_sahyadri_SDC-26-27-0418_resubmitted_scan.png),
creates nothing. Both tools add the agent's control log to the bill, so a reviewer can see why it was posted or
held.

#### The expense lane

Expense receipts, such as [`08_receipt_hotel_sabarmati.pdf`](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agentic-accounts-payable/samples/08_receipt_hotel_sabarmati.pdf), follow
the same pattern. The `classify_expense` prompt node picks the expense category (local travel, hotel, meals,
airfare or other) and the likely business purpose. The `expense_controls` tool node then checks the receipt
against the expense policy and Odoo: the employee and their corporate card, the category limit, how old the
receipt is, duplicate claims and GST input-credit eligibility. The rules are in
[`wxo/tools/apcore/expenses.py`](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agentic-accounts-payable/wxo/tools/apcore/expenses.py).

The `route_expense` decision table blocks duplicates and sends any failed control to the manager. Approving and
holding call the same tool, `ap_book_expense`, with a different value for `approve`:

```python
approve = aflow.tool("ap_book_expense", name="approve_expense", display_name="Approve expense in Odoo")
hold_exp = aflow.tool("ap_book_expense", name="hold_expense", display_name="Hold expense for manager")
for node, ok in ((approve, "True"), (hold_exp, "False")):
    node.map_input("receipt", 'flow["identify_document"].output.fields')
    node.map_input("control_result", 'flow["expense_controls"].output.result')
    node.map_input("approve", ok)
```

#### Purchase-order copies and delivery challans

These two lanes have one tool node each, and both take the normalised fields from `identify_document`:

```python
verify = aflow.tool("ap_verify_po", name="verify_po", display_name="Verify PO against Odoo")
receive = aflow.tool("ap_receive_goods", name="receive_goods", display_name="Receive goods (GRN) in Odoo")
for node in (verify, receive):
    node.map_input("document", 'flow["identify_document"].output.fields')
```

`verify_po` compares a supplier-signed PO copy, such as
[`11_po_copy_MSC-PO-26-0161.pdf`](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agentic-accounts-payable/samples/11_po_copy_MSC-PO-26-0161.pdf), with the PO in Odoo and logs the
result on it. `receive_goods` books the goods on a challan, such as
[`12_challan_narmada_NPI-DC-1190.pdf`](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agentic-accounts-payable/samples/12_challan_narmada_NPI-DC-1190.pdf), against the open goods
receipt when the quantities fit, and flags any bill that was held because those goods hadn't arrived. The logic for both is in
[`wxo/tools/apcore/receiving.py`](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agentic-accounts-payable/wxo/tools/apcore/receiving.py).

#### Task 3. Send each document type to its lane

All the lanes now exist, so you can connect them. Replace the line `by_type = todo(...)` with this code:

```python
by_type = aflow.branch(name="document_type", display_name="Document type",
                       evaluator='flow["identify_document"].output.doc_type')
(by_type.case("supplier_invoice", checks).case("expense_receipt", category)
 .case("purchase_order", verify).case("delivery_challan", receive).case("other", END))
```

The branch reads the document type from `identify_document` and sends the document to the first node of its
lane. Anything the flow doesn't handle, such as the price-revision letter
[`13_letter_konkan_price_revision.pdf`](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agentic-accounts-payable/samples/13_letter_konkan_price_revision.pdf), goes to `END` and is
left for a person.

#### Connect the nodes and map the outputs

The end of the file chains the nodes in order and sends every final tool node to `END`:

```python
aflow.sequence(START, read, identify, by_type)
aflow.sequence(checks, classify, erp, decide, route)
aflow.sequence(category, exp, decide_exp, route_exp)
```

It then maps each output of the flow, such as the route, the controls and the Odoo result, to the node that
produces it. A document passes through only one lane, so the other lanes' outputs stay empty. Mapping every
output explicitly stops the runtime from trying to map them automatically, which can fail, and the route and its
reason get a default value. The workbench reads these outputs to show the result.

#### Check your work

Check the file for syntax errors. The command prints nothing when the file is valid:

```bash
.venv/bin/python -m py_compile wxo/flows/starter/ap_document_processing_flow.py
```

You deploy your flow in Step 8. If a task is still missing, the deploy stops and tells you which one.

#### Try it yourself

When you finish the tutorial, come back and try these changes. Reset the workbench before you process the samples
again.

- **Change the limit without code.** In the flow editor, lower the touchless limit in the AP routing policy to
  300000, then process [`01_sahyadri_SDC-26-27-0418.pdf`](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agentic-accounts-payable/samples/01_sahyadri_SDC-26-27-0418.pdf). Its total
  is ₹3,58,956, so it is now held for review.
- **Add a rule.** Hold invoices when the model is unsure of the nature of payment. Add this rule after the
  duplicate rule in Task 2 and redeploy:

  ```python
  rule("classify_payment", ("confidence", DecisionsCondition().less_than(0.8)), "exception",
       "TDS classification needs review"),
  ```

- **Change the prompt.** In `TDS_SYSTEM_PROMPT`, remove "engineering, process-safety or HAZOP studies," and
  process [`02_kaveri_KPA-26-27-073.pdf`](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agentic-accounts-payable/samples/02_kaveri_KPA-26-27-073.pdf) again. The model might now call
  the HAZOP study a technical service, which changes the TDS rate from 10% to 2%.
- **Add a document type.** Add a credit-note schema and a case for it in Task 3, then process a credit note of
  your own.

### Step 8. Deploy the solution to watsonx Orchestrate

In this step, you deploy the connection, tools, flow, model policy, agents and controls with one script.

1. Run the deploy script from the project root. `FLOW_FILE` tells it to import the flow you completed in Step 7:

   ```bash
   ORCH=.venv/bin/orchestrate FLOW_FILE=flows/starter/ap_document_processing_flow.py ./wxo/deploy.sh
   ```

   The script prints a line for each stage, followed by the ADK's messages for each item it imports:

   ```output
   ▸ Connection: odoo_erp (key-value, team credentials)
   ▸ Tools (Odoo via connection; the flow's process tools first)
   ▸ Flow: ap_document_processing_flow (flows/starter/ap_document_processing_flow.py)
   ▸ Model policy: Claude Sonnet 4.6 primary, gpt-oss-120b fallback
   ▸ Agents
   ▸ Controls (control plane)
   Done.
   ```

   The order matters. The flow's tools are imported before the flow, because the flow reads their schemas when
   it is imported. To deploy the finished flow instead of yours, leave out `FLOW_FILE`.

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
<summary>The deploy stops with "Step 7, Task … is not done yet"</summary>

The starter flow still has a `todo(...)` line for that task. Complete the task as described in Step 7 and run the
deploy script again, or leave out `FLOW_FILE` to deploy the finished flow.
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
[GitHub repository](https://github.com/IBM/oic-i-agentic-ai-tutorials/tree/main/i-oic-agentic-accounts-payable).

To learn more, see the [watsonx Orchestrate ADK documentation](https://developer.watson-orchestrate.ibm.com/).

## Acknowledgments

This tutorial was produced as part of the IBM Open Innovation Community initiative: Agentic AI (AI for Developers
and Ecosystem).

The author (Aditya Krishnan) deeply appreciates the support of Ela Dixit and Bindu Umesh for reviewing and
contributing to this tutorial.
