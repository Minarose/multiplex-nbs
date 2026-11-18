function [pvals, sigTable, report] = mnbs_summarize(clustersObs, nullMaxCluster, opts)
%MNBS_SUMMARIZE Corrected p-values and a summary of observed components.
%
%   [pvals, sigTable, report] = mnbs_summarize(clustersObs, nullMax)
%   [pvals, sigTable, report] = mnbs_summarize(clustersObs, nullMax, opts)
%
%   p_FWE = (1 + number of permutation maxima >= observed) / (nPerm + 1).
%
%   Inputs
%     clustersObs  observed components (MNBS_COMPONENTS)
%     nullMax      largest component statistic in each permutation
%     opts         struct: .alpha [0.05], .alphaStrict [0.01],
%                  .usePlusOne [true], .verbose [true], .sortBy ['stat'],
%                  .nullPercentiles [50 90 95 99]
%
%   Outputs
%     pvals     corrected p-value of each observed component
%     sigTable  table of components with p_FWE <= alpha
%     report    struct: counts, null-distribution percentiles and settings
%
%   See also MNBS_ANALYZE, MNBS_PERMUTE.
%
%   Original implementation: Darren S. Kadis (March 2026).
%   Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
%   https://github.com/Minarose/multiplex-nbs

% ------------------------------ defaults
if nargin < 3, opts = struct(); end
if ~isfield(opts,'alpha'),          opts.alpha = 0.05; end
if ~isfield(opts,'alphaStrict'),    opts.alphaStrict = 0.01; end
if ~isfield(opts,'usePlusOne'),     opts.usePlusOne = true; end
if ~isfield(opts,'verbose'),        opts.verbose = true; end
if ~isfield(opts,'sortBy'),         opts.sortBy = 'stat'; end
if ~isfield(opts,'nullPercentiles'), opts.nullPercentiles = [50 90 95 99]; end

nObs = numel(clustersObs);
nPerm = numel(nullMaxCluster);
if nPerm < 1 || any(~isfinite(nullMaxCluster(:))) || any(nullMaxCluster(:)<0)
    error('The null distribution must contain finite nonnegative permutation maxima.');
end
pvals = nan(1,nObs);

nullSummary = local_null_summary(nullMaxCluster, opts.nullPercentiles);

% ------------------------------ no observed clusters
if nObs == 0
    sigTable = table();
    report = struct( ...
        'rejectNull', false, ...
        'nObserved', 0, ...
        'nPerm', nPerm, ...
        'nSig', 0, ...
        'nSigStrict', 0, ...
        'alpha', opts.alpha, ...
        'alphaStrict', opts.alphaStrict, ...
        'clusterMetric', '', ...
        'maxObsStat', 0, ...
        'nNullGEmaxObs', 0, ...
        'nullSummary', nullSummary);

    if opts.verbose
        fprintf('\n============================================================\n');
        fprintf('Node-layer result\n');
        fprintf('============================================================\n');
        fprintf('Observed clusters: 0\n');
        fprintf('Permutations: %d\n', nPerm);
        fprintf('Decision (FWE, alpha = %.2f): FAIL TO REJECT the null.\n', opts.alpha);
        fprintf('No observed clusters were detected.\n');
        fprintf('\nNull max-cluster distribution summary\n');
        fprintf('------------------------------------------------------------\n');
        local_print_null_summary(nullSummary);
    end
    return
end

% ------------------------------ inferential metric
if isfield(clustersObs, 'clusterMetric') && ~isempty(clustersObs(1).clusterMetric)
    metricName = clustersObs(1).clusterMetric;
else
    metricName = 'unknown';
end

% ------------------------------ observed cluster statistics and p-values
obsStat = [clustersObs.testStat];
maxObsStat = max(obsStat);

for k = 1:nObs
    if opts.usePlusOne
        pvals(k) = (1 + sum(nullMaxCluster >= obsStat(k))) / (nPerm + 1);
    else
        pvals(k) = mean(nullMaxCluster >= obsStat(k));
    end
end

% ------------------------------ sorting and reporting mask
switch lower(opts.sortBy)
    case 'stat'
        [~,ord] = sort(obsStat,'descend');
    case 'p'
        [~,ord] = sort(pvals,'ascend');
    otherwise
        error('Unknown sortBy: %s', opts.sortBy);
end

clustersOrd = clustersObs(ord);
pvalsOrd = pvals(ord);

sigMask = pvalsOrd <= opts.alpha;
sigStrictMask = pvalsOrd <= opts.alphaStrict;

sigTable = local_make_table(clustersOrd(sigMask), pvalsOrd(sigMask));

% ------------------------------ package report
report = struct();
report.rejectNull = any(sigMask);
report.nObserved = nObs;
report.nPerm = nPerm;
report.nSig = sum(sigMask);
report.nSigStrict = sum(sigStrictMask);
report.alpha = opts.alpha;
report.alphaStrict = opts.alphaStrict;
report.clusterMetric = metricName;
report.maxObsStat = maxObsStat;
report.nNullGEmaxObs = sum(nullMaxCluster >= maxObsStat);
report.nullSummary = nullSummary;

% convenience aliases for easy access
report.nullMedian = nullSummary.median;
report.nullP90 = nullSummary.p90;
report.nullP95 = nullSummary.p95;
report.nullP99 = nullSummary.p99;
report.maxNullStat = nullSummary.max;

% ------------------------------ print summary
if opts.verbose
    fprintf('\n============================================================\n');
    fprintf('Node-layer result\n');
    fprintf('============================================================\n');
    fprintf('Observed clusters: %d\n', report.nObserved);
    fprintf('Permutations: %d\n', report.nPerm);
    fprintf('Inferential cluster metric: %s\n', report.clusterMetric);
    fprintf('Largest observed statistic: %.4f\n', report.maxObsStat);
    fprintf('\nNull max-cluster distribution summary\n');
    fprintf('------------------------------------------------------------\n');
    local_print_null_summary(nullSummary);
    fprintf('Num null >= largest observed: %d\n', report.nNullGEmaxObs);
    fprintf('\n');

    if report.rejectNull
        fprintf('Decision (FWE, alpha = %.2f): REJECT the null.\n', opts.alpha);
        fprintf('%d cluster(s) survived FWE correction at p <= %.2f.\n', report.nSig, opts.alpha);
    else
        fprintf('Decision (FWE, alpha = %.2f): FAIL TO REJECT the null.\n', opts.alpha);
        fprintf('No cluster statistic exceeded the null distribution at p <= %.2f (FWE-corrected).\n', opts.alpha);
    end

    if report.nSigStrict == 0
        fprintf('At the stricter threshold p <= %.2f (FWE), no clusters survived.\n', opts.alphaStrict);
    else
        fprintf('%d cluster(s) survived FWE correction at p <= %.2f.\n', report.nSigStrict, opts.alphaStrict);
    end

    if report.nSig > 0
        fprintf('\nSignificant node-layer clusters\n');
        fprintf('------------------------------------------------------------\n');
        for k = 1:height(sigTable)
            fprintf(['Cluster %d | p_FWE = %.4f | extent = %d | mass = %.4f | testStat = %.4f ' ...
                     '| metric = %s | layer indices = %d-%d | nNodes = %d | nLayers = %d\n'], ...
                sigTable.id(k), sigTable.p_FWE(k), sigTable.extent(k), sigTable.mass(k), ...
                sigTable.testStat(k), sigTable.clusterMetric{k}, ...
                sigTable.freqMin(k), sigTable.freqMax(k), ...
                sigTable.nNodes(k), sigTable.nFreqBins(k));
            fprintf('  Nodes: [%s]\n', sigTable.nodeList{k});
        end
    end
end
end

% ========================================================================
function T = local_make_table(clusters, pvals)
if isempty(clusters)
    T = table();
    return
end

nodeList = cell(numel(clusters),1);
clusterMetric = cell(numel(clusters),1);

for k = 1:numel(clusters)
    nodeList{k} = strtrim(sprintf('%d ', clusters(k).nodes(:)));
    clusterMetric{k} = clusters(k).clusterMetric;
end

T = table( ...
    [clusters.id]', ...
    [clusters.nNodes]', ...
    [clusters.nFreqBins]', ...
    arrayfun(@(c) min(c.freqBins), clusters)', ...
    arrayfun(@(c) max(c.freqBins), clusters)', ...
    [clusters.extent]', ...
    [clusters.mass]', ...
    [clusters.testStat]', ...
    pvals(:), ...
    clusterMetric, ...
    nodeList, ...
    'VariableNames', {'id','nNodes','nFreqBins','freqMin','freqMax', ...
                      'extent','mass','testStat','p_FWE','clusterMetric','nodeList'});
end

% ========================================================================
function s = local_null_summary(nullMaxCluster, percentiles)
if isempty(nullMaxCluster)
    s = struct('median',0,'p90',0,'p95',0,'p99',0,'max',0,'percentiles',percentiles,'values',zeros(size(percentiles)));
    return
end

values = sort(nullMaxCluster(:));
positions = min(max(0.5 + numel(values)*percentiles/100, 1), numel(values));
if numel(values)==1
    vals = repmat(values, size(percentiles));
else
    vals = interp1(1:numel(values), values, positions);
end

s = struct();
s.percentiles = percentiles(:)';
s.values = vals(:)';
s.median = local_get_percentile(vals, percentiles, 50);
s.p90 = local_get_percentile(vals, percentiles, 90);
s.p95 = local_get_percentile(vals, percentiles, 95);
s.p99 = local_get_percentile(vals, percentiles, 99);
s.max = max(nullMaxCluster);
end

% ========================================================================
function v = local_get_percentile(vals, percentiles, target)
idx = find(percentiles == target, 1);
if isempty(idx)
    v = NaN;
else
    v = vals(idx);
end
end

% ========================================================================
function local_print_null_summary(s)
if ~isnan(s.median), fprintf('Median null max: %.4f\n', s.median); end
if ~isnan(s.p90),    fprintf('90th percentile null max: %.4f\n', s.p90); end
if ~isnan(s.p95),    fprintf('95th percentile null max: %.4f\n', s.p95); end
if ~isnan(s.p99),    fprintf('99th percentile null max: %.4f\n', s.p99); end
fprintf('Max null max: %.4f\n', s.max);
end
