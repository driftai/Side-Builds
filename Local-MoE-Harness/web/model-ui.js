(function attachModelUi(root) {
  function availabilityLabel(model) {
    if (model.active) return 'Ready';
    if (model.availability === 'installed') return 'Installed';
    if (model.availability === 'available') return 'Available · not installed';
    if (model.availability === 'not_tested') return 'Not tested on this runtime';
    if (model.availability === 'not_viable') return 'Not recommended on this hardware';
    return 'Unavailable';
  }

  function validationLabel(value) {
    if (value === 'primary') return 'Primary';
    if (value === 'validated') return 'Validated alternate';
    if (value === 'windows_validated') return 'Windows validated';
    if (value === 'windows_setup_required') return 'Setup refresh required';
    if (value === 'windows_candidate') return 'Windows qualification candidate';
    if (value === 'platform_blocked') return 'Platform blocked';
    if (value === 'experimental') return 'Experimental';
    if (value === 'not_viable') return 'Not viable';
    return 'Not tested';
  }

  function actionForModel(model, switching) {
    if (switching) return {label: 'Switch in progress', enabled: false};
    if (model.active) return {label: 'Active', enabled: false};
    if (model.selectable && model.installed) return {label: 'Switch', enabled: true};
    if (!model.selectable && model.validation === 'windows_setup_required') return {label: 'Run Setup.bat', enabled: false};
    if (model.installed && !model.selectable) return {label: 'Compatibility blocked', enabled: false};
    if (!model.selectable && model.validation === 'platform_blocked') return {label: 'Compatibility blocked', enabled: false};
    if (model.download_supported) return {label: 'Install from terminal', enabled: false};
    return {label: 'Unavailable', enabled: false};
  }

  function switchStageLabel(stage, targetName, previousName) {
    const target = targetName || 'new model';
    const previous = previousName || 'previous model';
    const labels = {
      stopping_previous: `Stopping ${previous}…`, stopping: `Stopping ${previous}…`, stopped: `Starting ${target}…`,
      starting_target: `Starting ${target}…`, loading_weights: `Loading ${target} weights…`,
      checking_identity: `Checking ${target} identity and readiness…`, committing_selection: `Saving ${target} selection…`,
      restoring_previous: `Restoring ${previous}…`, ready: `${target} ready`, restored: `${previous} restored`,
      restore_failed: 'Model recovery failed'
    };
    return labels[stage] || `Switching to ${target}…`;
  }

  function streamDeltaChannels(delta) {
    const value = delta || {};
    return {content: typeof value.content === 'string' ? value.content : '', reasoning: typeof value.reasoning_content === 'string' ? value.reasoning_content : ''};
  }

  const api = {availabilityLabel, validationLabel, actionForModel, switchStageLabel, streamDeltaChannels};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.LocalMoeModelUi = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
