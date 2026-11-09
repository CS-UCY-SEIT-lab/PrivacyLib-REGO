# GDPR Policy Enforcement with OPA, Python, JavaScript & PHP

OPA and the shared Rego policies make GDPR decisions. Applications handle the
returned action plans, including database changes, downloads, and notifications.

## Layout

~~~text
gdpr/                         Shared Rego policies and input.json
python/                       Original Python application and OPA client
javascript/
  src/gdpr-router.js           JavaScript router
  cli.js                      JavaScript command-line runner
php/
  src/GdprRouter.php           PHP router
  cli.php                     PHP command-line runner
tests/
  python/run_rego_tests.py     Original Python scenarios and runner
  javascript/run_rego_tests.js Native JavaScript port
  php/run_rego_tests.php       Native PHP port
  fixtures/
    scenarios.json            Exported original scenarios and assertions
    inputs/                   Original representative input fixtures
examples/                     Additional Rego examples
outputs/                      Generated application artifacts
privacyLibInputGenerator.html Input generator
~~~

Run the commands below from the repository root.

## Applications

Start OPA for the application clients:

~~~sh
opa run --server --watch gdpr/
~~~

Python requires Python 3.10+ and the dependencies in python/requirements.txt:

~~~sh
pip install -r python/requirements.txt
python python/appMain.py
~~~

The original Python demo selects workflows in its main() function.

JavaScript requires Node.js 18+. PHP requires PHP 8.0+ with cURL for HTTP
requests. Neither router needs additional packages.

~~~sh
node javascript/cli.js consent gdpr/input.json 1
php php/cli.php consent gdpr/input.json 1
node javascript/cli.js erasure gdpr/input.json
php php/cli.php erasure gdpr/input.json
~~~

Supported operations are consent, lawful, information, access, rectification,
erasure, restriction, portability, objection, breach, and complaint. The first
five require a string user ID. The others read their requests from the input
object using the existing gdpr/input.json schema. The input file defaults to
gdpr/input.json when omitted.

Library usage:

~~~js
const { GdprRouter } = require('./javascript/src/gdpr-router');
const input = require('./gdpr/input.json');

async function access() {
  return new GdprRouter().route('access', input, '1');
}
~~~

~~~php
require_once 'php/src/GdprRouter.php';
$input = json_decode(file_get_contents('gdpr/input.json'), false, 512, JSON_THROW_ON_ERROR);
$result = (new GdprRouter())->route('access', $input, '1');
~~~

Consent and lawful processing return booleans. Information, access, and
rectification return policy objects. Other operations return
{decision, justification, actions}. Undefined decisions default to reject
(no_notify for breach); undefined boolean results default to false.

HTTP, connection, and JSON failures raise errors. CLI errors go to stderr and
produce a nonzero exit status. Set OPA_QUERY_URL to change the endpoint, or
pass the URL and timeout to the router constructor. The default timeout is
10 seconds per request.

The JavaScript and PHP erasure routes use data.erasure, matching
gdpr/erasure.rego. The original Python HTTP client still uses
data.privacy.erasure.

## Original tests in all three languages

The existing Python suite is the source for all 139 scenarios. Its JavaScript
and PHP ports use the same mutated inputs, Rego expressions, expected assertions,
and scenario coverage checklist. No separate set of test scenarios was added.

Each runner loads the full gdpr/ policy directory through the OPA executable.
Tests require opa on PATH, but do not require a running OPA server or application
HTTP dependencies. These are the original Rego policy tests; they do not test
the language routers' HTTP transport or application side effects.

~~~sh
python tests/python/run_rego_tests.py
node tests/javascript/run_rego_tests.js
php tests/php/run_rego_tests.php
~~~

Each runner prints PASS/FAIL per scenario, the total, and the coverage checklist.
It exits nonzero if a scenario fails or an expected coverage item is missing.

The JavaScript and PHP runners read the checked-in fixtures/scenarios.json,
which contains assertions exported from Python, not answers observed from OPA.
They run independently of Python.

When changing Python scenarios, mutations, assertions, coverage items, or the
base input, regenerate the shared file:

~~~sh
python tests/python/run_rego_tests.py --export
~~~

The export does not require OPA. It preserves equality, nested field checks,
membership/substring checks, counts, any-item predicates, combined assertions,
and undefined Rego results represented as null.

The Python runner continues to generate the 26 representative JSON input files
under tests/fixtures/inputs/.
