# Quote input forwarding repair

The production scanner passes `os.environ` to 0x and Kyber, but its workflow
previously forwarded only Telegram credentials. Repository secrets/variables do
not automatically become runner environment variables. Thus setting quote inputs
in GitHub settings alone could not enable those adapters.

The scanner step now forwards the existing optional inputs explicitly:

| Name | GitHub setting | Meaning |
| --- | --- | --- |
| ZEROX_API_KEY | Actions secret | Provider authentication, if available |
| ORACLE_TAKER_ADDRESS | Actions variable or secret | Public EVM address for unsigned quote research |
| ORACLE_FUNDING_TOKEN | Actions variable or secret | Exact funding-token contract on the research network |
| ORACLE_ORDER_BASE_UNITS | Actions variable or secret | Explicit positive funding amount in token base units |

No credentials are created, purchased, changed or printed. Never provide a private
key or seed phrase. A quote request cannot sign or submit a transaction. Use only
an already authorized provider account; this change does not establish a service
subscription or approve any token or order size.

`execution_configuration.status` emits only missing/invalid setting names. Present
inputs are labelled INPUTS_PRESENT_UNVERIFIED, never executable or trade-ready.
The diagnostics are logged before the scan and retained in hourly evidence.
Funding, allowance, chain, exact route, fees and independent sellability remain
separate mandatory checks. A single funding-token address is not a cross-chain
funding configuration.

Local validation: compileall and 532 unittest tests passed, including missing
inputs, zero addresses, invalid sizes, value non-disclosure and workflow forwarding.
Live provider access and production outcomes must be verified separately.
