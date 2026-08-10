# RLM-Powered Data Processor Agent

A watsonx.ai-powered agent implementing the **Scan, Delegate, and Combine** approach for efficient document processing using Retrieval-augmented Language Model (RLM) techniques on the bank loan document.

## 🎯 Overview

This agent demonstrates the RLM methodology for processing large documents efficiently:

1. **SCAN Phase**: Searches the document and finds relevant sections (enforces a minimum threshold of **5 sections** for parallel demonstration).
2. **DELEGATE Phase**: Creates sub-agents that process sections in parallel (minimum of **5 sub-agents**).
3. **COMBINE Phase**: Synthesizes results into a final answer, returning the answer first followed by a detailed metrics table.

### Benefits of RLM Approach

- ✅ **Reduced Memory Usage**: Only relevant sections are processed
- ✅ **Improved Accuracy**: Focused analysis on pertinent content
- ✅ **Parallel Processing**: Multiple sub-agents work simultaneously
- ✅ **Metrics Transparency**: Displays execution metrics such as iterations, tokens, coverage, and speedup.

---

## 📄 Target Document

The agent processes: **[bank_loan_document.pdf](bank_loan_document.pdf)** (10-page bank loan agreement containing structured loan metadata, borrower information, collateral details, and terms).

---

## 🏗️ Architecture

```
START → SCAN → DELEGATE → COMBINE → END
```

### Phase 1: SCAN 🔍
* **Purpose**: Find relevant document sections.
* **Process**:
  1. Load PDF document.
  2. Split into chunks (2000 chars, 200 overlap).
  3. Evaluate relevance using watsonx.ai.
  4. **Threshold Guard**: If fewer than 5 sections are identified as relevant, the agent automatically supplements with additional chunks to ensure exactly 5 chunks are retrieved.

### Phase 2: DELEGATE 🤖
* **Purpose**: Parallel processing by specialized sub-agents.
* **Process**:
  1. Spawns 5 independent sub-agents.
  2. Sub-agents analyze their respective sections without hallucinating or fabricating details (using anti-hallucination prompts).

### Phase 3: COMBINE 🔗
* **Purpose**: Synthesize the final answer and calculate execution metrics.
* **Process**:
  1. Consolidates sub-agent reports.
  2. Compiles a detailed markdown execution metrics table (scanning iterations, active sub-agents, token usage, compression ratio, memory savings, etc.).

---

## 🚀 Setup & Installation

Navigate to the agent directory and install dependencies:

```bash
cd rlm_data_processor
pip install -r requirements.txt
```

---

## 💬 Sample Queries

Once deployed, query the agent via the coordinator about the bank loan document details:
* *"What is the loan account number and who is the borrower?"*
* *"Who is the Relationship Manager assigned to the borrower?"*
* *"What security or collateral is provided for this loan?"*
* *"What is the monthly salary of John Anderson?"*
* *"What is the final authorization code for this loan document?"*

---

## 📊 Performance Metrics Table (Example Output)

When you query the agent, it will return the answer followed by a metrics table (these values vary dynamically, e.g., showing 4, 5, 6, or 8 iterations and sub-agents, depending on the query):

| Metric | Value | Description |
| :--- | :--- | :--- |
| **Scanning Iterations** | 5 | Number of sequential evaluations performed in the Scan Phase |
| **Active Sub-Agents** | 5 | Parallel workers spawned to analyze relevant sections |
| **Total Processed Tokens** | 5,670 | Total token throughput across scan, delegate, and combine phases |
| **Document Coverage** | 100.0% | Proportion of the PDF scanned and evaluated |
| **Context Compression** | 0.0% | Irrelevant context filtered out before the Delegate Phase |
| **Latency Speedup (Est.)** | 5.0x | Ideal execution speed multiplier from parallel sub-agents |
| **Memory Savings** | 0.0 KB | Memory saved by excluding non-relevant document chunks |
| **Estimated API Cost** | $0.014175 | Approximate watsonx.ai token usage cost |