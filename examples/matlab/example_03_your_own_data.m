%% Bringing your own data (MATLAB)
% Every participant needs the same regions in the same order.

addpath(fullfile(pwd, 'matlab'));

% Option 1: a cell array, one regions x regions x layers matrix per participant.
nSubj = 30; nRegions = 20; nLayers = 6;
W = cell(nSubj, 1);
rng(1);
for s = 1:nSubj
    M = randn(nRegions, nRegions, nLayers);
    W{s} = (M + permute(M, [2 1 3])) / 2;      % matrices must be symmetric
end
group = [ones(15, 1); 2 * ones(15, 1)];        % numeric group labels

opts = struct('t0', 3, 'nPerm', 499, 'axisName', 'Frequency', 'axisUnit', 'Hz', ...
              'axisValues', [4 8 13 20 30 45]);
result = mnbs_analyze(W, group, opts);
fprintf('%d components observed, %d significant\n', numel(result.clusters), height(result.significant));

% Option 2: save a file the Python package and the desktop app can open too.
% Use the -v7 format (v7.3/HDF5 is not supported).
axisValues = opts.axisValues; axisName = 'Frequency'; axisUnit = 'Hz';
nodeLabels = arrayfun(@(k) sprintf('Region %d', k), 1:nRegions, 'UniformOutput', false);
save('my_study.mat', 'W', 'group', 'axisValues', 'axisName', 'axisUnit', 'nodeLabels', '-v7');
% Python: multiplex_nbs.load_dataset('my_study.mat'); app: Data > Open my data.
