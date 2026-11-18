%% Multiplex-NBS quick start (MATLAB)
% Run from the repository folder. Adds the toolbox to the path, loads the
% bundled brain demo and runs Multiplex-NBS.
%
% The demo is an open human structural connectome (32 regions) with 40
% simulated participants in two groups and 8 time windows (0-350 ms).
% Group 1 was simulated to be higher along a left sensorimotor-parietal
% chain at 100-200 ms.

addpath(fullfile(pwd, 'matlab'));

d = mnbs_load_demo('brain-network');
fprintf('%d observations, %d regions, %d time windows\n', ...
    numel(d.W), size(d.W{1}, 1), size(d.W{1}, 3));

% Choose the threshold, tail and component measure before looking at results.
% Use at least 5000 permutations for anything you report; 999 keeps this fast.
opts = struct( ...
    't0', 3, ...                       % primary threshold on the t statistic
    'tail', 'right', ...               % group 1 > group 2
    'clusterMetric', 'extent', ...     % component size = number of region-time sites
    'layerAdjacency', 'consecutive', ...% Multiplex-NBS: link a region to itself over time
    'nPerm', 999, 'rngSeed', 1, ...
    'axisName', d.axisName, 'axisUnit', d.axisUnit, 'axisValues', d.axisValues);

result = mnbs_analyze(d.W, d.group, opts);

% Significant components (corrected p <= opts.alpha)
disp(result.significant)

% Details of each significant component
for k = find(result.pvalues <= 0.05)
    c = result.clusters(k);
    times = result.axis.values(c.layerBins);
    fprintf('Component %d: p_FWE = %.3g, %d sites, %d regions, %g-%g %s\n', ...
        c.id, c.p_FWE, c.extent, numel(c.nodes), times(1), times(end), result.axis.unit);
    fprintf('  regions: %s\n', strjoin(d.nodeLabels(c.nodes), ', '));
end

save('quickstart_result.mat', 'result');
