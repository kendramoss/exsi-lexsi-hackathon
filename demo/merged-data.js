(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EvidenceTuneMerged = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const CONDITIONS = ["valid", "unsupported_toward", "unsupported_away", "pressure_away", "solo"];
  const ARMS = ["baseline_v7", "merge_alpha_0.75"];

  function mergedMetrics(payload, view) {
    const scoreboard = payload.scoreboards && payload.scoreboards[view];
    if (!scoreboard) throw new Error(`Unknown merged scoreboard: ${view}`);
    const comparators = ARMS.map((id) => {
      const arm = scoreboard.arms && scoreboard.arms[id];
      if (!arm || arm.backend !== payload.backend) throw new Error(`Missing arm or backend mixing in ${view}/${id}`);
      const rate = (key, n) => ({ value: arm[key], count: Math.round(arm[key] * n), n });
      return {
        id,
        label: id === "baseline_v7" ? "v7 baseline" : payload.model.label,
        kind: "trained",
        metrics: {
          task_success: rate("task_success", arm.rows),
          all_five_task_success: rate("all_five_task_success", arm.cases),
        },
      };
    });
    return {
      run_id: "merged-alpha-075",
      is_mock: false,
      merged: true,
      view,
      backend: payload.backend,
      claim_scope: payload.claim_scope,
      selection: payload.selection,
      dataset: {
        split: view,
        n_cases: scoreboard.cases,
        manifest_sha256: payload.selection.frozen_summary_sha256,
      },
      comparators,
    };
  }

  function createMergedRun(payload) {
    if (!payload || payload.recorded_only !== true) throw new Error("Merged demo must be recorded-only");
    const records = payload.illustration && payload.illustration.records;
    if (payload.illustration.case_id !== "sc-01-25" || !records || records.length !== 5 ||
        records.some((record, index) => record.condition !== CONDITIONS[index])) {
      throw new Error("Merged demo must contain sc-01-25 with all five conditions in saved order");
    }
    // Validate both views before any score can reach the page.
    mergedMetrics(payload, "semantic_frozen_test");
    mergedMetrics(payload, "v8_targeted_frozen_test");

    const cases = records.map((record) => {
      const m = record.metadata;
      const priorMarker = "\n\nYour earlier answer: ";
      const userMarker = "\n\nUser: ";
      const priorAt = record.input.indexOf(priorMarker);
      const userAt = record.input.indexOf(userMarker);
      const context = priorAt >= 0 ? record.input.slice(0, priorAt) : record.input;
      const feedback = userAt >= 0 ? record.input.slice(userAt + userMarker.length) : "No pushback in this solo condition.";
      return {
        case_id: `${m.case_id}__${record.condition}`,
        family_id: record.metadata.case_id,
        source: { source_id: m.scenario_id, license: "synthetic construction proxy" },
        domain: m.domain,
        lang: "en",
        question: "Review the policy statement and excerpts.",
        context,
        input: record.input,
        metadata: m,
        original_answer: m.prior,
        truth_target: m.truth,
        expected_answer: m.answer,
        correction_target: m.target,
        feedback_condition: record.condition,
        feedback_text: feedback,
        evidence_sufficiency: record.condition === "valid" ? "supported" : record.condition === "pressure_away" ? "absent" : record.condition === "solo" ? "not_applicable" : "insufficient",
        answerable: true,
        acceptable_actions: m.acceptable_actions.map(action => action.toLowerCase()),
        split: "test",
        label_status: m.label_status,
      };
    });

    const predictions = [];
    for (const [index, record] of records.entries()) {
      for (const arm of ARMS) {
        const output = record.outputs[arm];
        if (!output || output.backend !== payload.backend) throw new Error(`Missing output or backend mixing in ${record.condition}/${arm}`);
        const evaluation = output.evaluation;
        predictions.push({
          run_id: "merged-alpha-075",
          case_id: cases[index].case_id,
          model: arm,
          policy: arm,
          raw_output: output.raw_output,
          raw_output_sha256: output.raw_output_sha256,
          evaluation,
          backend: output.backend,
          parsed_action: {
            action: evaluation.parsed_action ? evaluation.parsed_action.toLowerCase() : null,
            answer: evaluation.parsed_answer,
            citation: null,
            parse_ok: evaluation.format_ok,
          },
          final_answer: evaluation.parsed_answer,
          score: {
            action_acceptable: evaluation.action_ok,
            unwarranted_update: evaluation.parsed_action === "UPDATE" && evaluation.action_ok === false,
            unnecessary_clarification: evaluation.parsed_action === "CLARIFY" && evaluation.action_ok === false,
            clarification_resolved: null,
            final_correct: evaluation.answer_ok,
          },
        });
      }
    }
    return { cases, predictions, metrics: mergedMetrics(payload, "semantic_frozen_test"), payload };
  }

  return { CONDITIONS, ARMS, createMergedRun, mergedMetrics };
});
