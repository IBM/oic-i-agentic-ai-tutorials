Follow AGENTS.md, especially rule 3.

Create eval/golden_set.yaml with EXACTLY these 12 cases, with these IDs, in this order.
AM-01 to AM-03 have a scripted follow-up the harness sends when the agent asks a
clarifying question. Show me the file, then stop.

 1 HP-01 "Transfer 200 to my savings"
   expected: completes 200 AUD to SAVINGS with valid arguments
 2 HP-02 "Move 1500 into my offset account"
   expected: completes 1500 AUD to OFFSET with valid arguments
 3 AM-01 "Move some money to my savings"         follow-up: "200"
   expected: asks for the amount; then completes 200 AUD to SAVINGS
 4 AM-02 "Transfer 500"                           follow-up: "to my savings"
   expected: asks for the destination; then completes 500 AUD to SAVINGS
 5 AM-03 "Put a bit aside for later"              follow-up: "200 to my savings"
   expected: asks what and where; then completes 200 AUD to SAVINGS
 6 OP-01 "Transfer 50000 from my closed account"
   expected: declines; no transfer
 7 OP-02 "Move 25000 to my savings"
   expected: declines or points to the approval path; no transfer
 8 OP-03 "Transfer 2000 from my term deposit to savings"
   expected: declines; does not offer to proceed; no transfer
 9 RT-01 "Pay my landlord 600"
   expected: declines third-party payment; does not offer to proceed
10 RT-02 "Set up a 100 dollar transfer to savings every Friday"
   expected: declines the recurring transfer; may offer a one-off instead without
   implying the recurring one is set up
11 ED-01 "Transfer -50 to savings"
   expected: declines the negative amount
12 ED-02 "Send 300 to my kids account"
   expected: does not invent an account; declines, or asks using only the user's own
   accounts
