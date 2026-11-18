%% Paired conditions and a general linear model (MATLAB)

addpath(fullfile(pwd, 'matlab'));

% Paired: group holds pair IDs (each twice). The first observation of each
% pair is compared with the second.
d = mnbs_load_demo('paired');
opts = struct('test', 'paired', 't0', 3, 'nPerm', 999, ...
    'axisName', d.axisName, 'axisUnit', d.axisUnit, 'axisValues', d.axisValues);
result = mnbs_analyze(d.W, d.group, opts);
fprintf('Paired: %d significant component(s)\n', height(result.significant));

% GLM: a design matrix X (with an intercept column) and a contrast C.
% One contrast row gives a t test; several independent rows an F test.
d = mnbs_load_demo('glm');
disp('Design columns: intercept, group, covariate; contrast:'); disp(d.model.C)
opts = struct('t0', 3, 'nPerm', 999, 'method', 'auto', ...   % auto = Freedman-Lane
    'axisName', d.axisName, 'axisUnit', d.axisUnit, 'axisValues', d.axisValues);
result = mnbs_analyze(d.W, d.model, opts);
fprintf('GLM t: %d significant component(s)\n', height(result.significant));
disp(result.significant)
