## CI/CD test

### threshold_validation.py
This check runs the validation framework with this config `agent_validation/config/adk_smoke_validation_config.yaml` to check if the resulting `Journey Success` is over a specified threshold.

## Preparing for ADK version upgrade

Steps to check framework compatibility with a newer version of ADK (ibm-watsonx-orchestrate)

1. Stop the server. Bump ADK version and restart.
```bash
orchestrate server stop
pip install --upgrade ibm-watsonx-orchestrate==<version>
orchestrate server start -l --env-file orders-team.env
# to check package version in python
python -c 'import ibm_watsonx_orchestrate;print(ibm_watsonx_orchestrate.__version__)'
# or directly using orchestrate
orchestrate --version
```

2. Run the framework with this config, and check for error output.
```bash
bash domains evals patch agent_validation/config/version_compatibility_config.yaml
```
A subset of the SAP test suites is used for this config.

If there's an error log like `Import command failed...`, it means that tool/agent import has failed. The import command will need to be updated to be compatible to proceed with the next round of testing.

If the script runs successfully, you should see logs similar to the following:


```log
[INFO]:DomainsValidation:Running test case: test_get_payslip_details
[DEBUG]:DomainsValidation:GENERATED_USER_MESSAGE:Give me payslip details for user 802982 between 2018-01-01 and 2018-01-31.
...
[DEBUG]:DomainsValidation:WXO: Here are the payslip details for user 802982 between 2018-01-01 and 2018-01-31:
...
```