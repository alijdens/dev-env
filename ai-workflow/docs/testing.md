# Testing Practices

These are general preferences; a repository's own testing docs take precedence when they conflict.

## Test each behavior once, at the right layer

Don't repeat the same test at every layer. A common anti-pattern: feature A gets a unit test in the lib, then the same test on the service consuming the lib, then again on the endpoint calling the service, and so on. This bloats PRs and makes changes expensive without adding confidence.

Instead:

- **Lower layers test functionality in detail.** Edge cases, error paths, and input combinations belong in the unit tests of the component that implements the logic.
- **Upper layers test integration.** Assume the components they use work correctly on their own (their tests prove that) and only check that they're wired together properly: the right component is called with the right inputs, and its outputs/errors are handled and propagated correctly. One or two representative cases are usually enough.
- **E2E tests only for critical flows.** An end-to-end test is worth it for features where a break would be severe (e.g. auth, payments, core user journeys). Most features don't need one.

### Example

A `parse_date` lib function used by a `ReportService`, exposed through a `/reports` endpoint:

- `parse_date` tests: valid formats, invalid formats, timezones, boundaries.
- `ReportService` tests: a valid date filters reports as expected; an invalid date surfaces the service's error. Don't re-test every date format.
- `/reports` endpoint tests: a valid request returns the report; the service error maps to the right HTTP status. Don't re-test service logic.

## Don't wait on real time

Tests must not depend on real sleeps or wall-clock time: they are slow, and they fail under load for reasons unrelated to the code. Raising a timeout or adding a delay is never the fix for a flaky test.

Make every wait deterministic instead:

- **Time**: use fake timers or an injectable clock and advance it explicitly.
- **Lazy or deferred work** (a lazy chunk, a background import): resolve it before the test starts, e.g. import the chunk before rendering.
- **Async jobs** (submit a job and wait for it to finish): mock the job with an event or promise that the test completes immediately, and await that. A timeout on the await is fine, but only as a guard so a bug doesn't block the whole run, never as the thing the test waits on.

### Example

```python
# Bad: waits for real time and fails when the machine is slow
submit_job()
time.sleep(2)
assert job_done()

# Good: the fake completes the job and signals it; the timeout only guards against hanging
done = threading.Event()
fake_queue.on_submit(lambda job: (job.finish(), done.set()))
submit_job()
assert done.wait(timeout=5)
assert job_done()
```
