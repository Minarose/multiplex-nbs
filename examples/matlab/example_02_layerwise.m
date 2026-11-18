%% Layer-wise NBS versus Multiplex-NBS (MATLAB)
% Layer-wise NBS keeps components within each time window and corrects across
% all windows at once; Multiplex-NBS lets a component continue across
% neighbouring windows. Choose one method in advance: running both and
% keeping the better result adds comparisons the correction does not cover.
% Classic NBS on a single network is available in Python (classic_nbs) and
% in the desktop app.

addpath(fullfile(pwd, 'matlab'));
d = mnbs_load_demo('brain-network');
base = struct('t0', 3, 'nPerm', 999, 'rngSeed', 1, ...
    'axisName', d.axisName, 'axisUnit', d.axisUnit, 'axisValues', d.axisValues);

methods = {'independent', 'Layer-wise NBS'; 'consecutive', 'Multiplex-NBS'};
for m = 1:size(methods, 1)
    opts = base;
    opts.layerAdjacency = methods{m, 1};
    result = mnbs_analyze(d.W, d.group, opts);
    fprintf('\n%s: %d of %d components significant\n', methods{m, 2}, ...
        height(result.significant), numel(result.clusters));
    if height(result.significant) > 0
        disp(result.significant(:, {'id', 'nNodes', 'freqMin', 'freqMax', 'extent', 'p_FWE'}))
    end
end
% freqMin and freqMax are layer indices; result.axis.values converts them to ms.
