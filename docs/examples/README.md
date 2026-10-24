# Examples

`minimal-inventory.csv` is the smallest valid input for `check_inventory` and `build_decision_pack`: the required header row and one synthetic system. It is a copy of the first row of the bundled toolkit fixture `automation/fixtures/valid-ai-inventory.csv`.

Use it as a starting point when `check_inventory` returns `MISSING_REQUIRED_COLUMN`: keep the header row, then replace the example row with your own systems. Column order does not matter. The system, owner, and use case shown are synthetic.

Passing this file produces reference results for human review. It does not approve, certify, or authorize anything (`authority_effect: NONE`).
