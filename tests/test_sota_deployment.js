const assert = require('assert');
const fs = require('fs');

// Exercise the actual deployment gate with mocked Actions responses.
const workflow = fs.readFileSync('.github/workflows/deploy.yml', 'utf8');
const match = workflow.match(/^          script: \|\n((?:            .*\n|\s*\n)+)/m);
assert.ok(match, 'Deployment gate script must exist');
const script = match[1].split('\n').map(line => line.slice(12)).join('\n');
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const gate = new AsyncFunction('context', 'github', script);
const normal = { name: 'Update SOTA snapshot', head_branch: 'final', status: 'completed', conclusion: 'success', id: 1 };

async function check(label, eventName, run, jobs, expected) {
    const context = { eventName, payload: { workflow_run: run }, repo: { owner: 'example', repo: 'survey' } };
    const github = { rest: { actions: { listJobsForWorkflowRun() {} } }, paginate: async () => jobs };
    assert.strictEqual(await gate(context, github), expected, label);
}

(async () => {
    const safe = [{ name: 'update-sota', conclusion: 'success' }];
    await check('ordinary push', 'push', null, [], true);
    await check('manual deployment', 'workflow_dispatch', null, [], true);
    await check('healthy refresh', 'workflow_run', normal, safe, true);
    await check('partial refresh with committed snapshot', 'workflow_run', { ...normal, conclusion: 'failure' }, safe, true);
    for (const conclusion of ['failure', 'cancelled', 'skipped', null]) {
        await check('unsafe snapshot job ' + conclusion, 'workflow_run', { ...normal, conclusion: 'failure' }, [{ name: 'update-sota', conclusion }], false);
    }
    await check('missing snapshot job', 'workflow_run', normal, [], false);
    await check('ambiguous snapshot job', 'workflow_run', normal, [...safe, ...safe], false);
    await check('wrong branch', 'workflow_run', { ...normal, head_branch: 'feature' }, safe, false);
    await check('cancelled workflow', 'workflow_run', { ...normal, conclusion: 'cancelled' }, safe, false);
    await check('unfinished workflow', 'workflow_run', { ...normal, status: 'in_progress' }, safe, false);
    await check('healthy paper update', 'workflow_run', { ...normal, name: 'Update Dynamic Papers' }, [], true);
    await check('failed paper update', 'workflow_run', { ...normal, name: 'Update Dynamic Papers', conclusion: 'failure' }, [], false);
    const research = { ...normal, name: 'Update Research Progress' };
    const researchSafe = [{ name: 'update-research', conclusion: 'success' }];
    await check('healthy research refresh', 'workflow_run', research, researchSafe, true);
    await check('partial research with committed data', 'workflow_run', { ...research, conclusion: 'failure' }, researchSafe, true);
    await check('research missing snapshot job', 'workflow_run', research, [], false);
    await check('research cannot borrow SOTA success', 'workflow_run', research, safe, false);
    await check('research wrong branch', 'workflow_run', { ...research, head_branch: 'feature' }, researchSafe, false);
    await check('research cancelled run', 'workflow_run', { ...research, conclusion: 'cancelled' }, researchSafe, false);
    await check('research unfinished run', 'workflow_run', { ...research, status: 'in_progress' }, researchSafe, false);
    for (const conclusion of ['failure', 'cancelled', 'skipped', null]) {
        await check('unsafe research job ' + conclusion, 'workflow_run', { ...research, conclusion: 'failure' }, [{ name: 'update-research', conclusion }], false);
    }
    await check('ambiguous research job', 'workflow_run', research, [...researchSafe, ...researchSafe], false);
    console.log('SOTA and research deployment gate tests OK');
})().catch(error => { console.error(error); process.exitCode = 1; });
