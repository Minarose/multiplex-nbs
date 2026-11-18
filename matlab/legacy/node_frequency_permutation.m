function [clustersObs, nullMaxCluster, statsObs] = node_frequency_permutation(W, groupLabels, opts)
% NODE_FREQUENCY_PERMUTATION
% Darren S. Kadis, PhD | 24MAR2026 | Toronto, Canada
% Permutation wrapper for node-frequency clustering.
%
% Notes
%   nullMaxCluster stores the permutation maximum of the selected
%   cluster metric:
%       - 'extent' : number of node-frequency sites
%       - 'mass'   : sum of node contributions
%
%   Default cluster metric is 'extent'.

% ------------------------------ defaults
if nargin < 3, opts = struct(); end
if ~isfield(opts,'nPerm'),         opts.nPerm = 1000; end
if ~isfield(opts,'t0'),            error('opts.t0 is required.'); end
if ~isfield(opts,'tail'),          error('opts.tail is required.'); end
if ~isfield(opts,'test'),          opts.test = 'two-sample'; end
if ~isfield(opts,'clusterMetric'), opts.clusterMetric = 'extent'; end
if ~isfield(opts,'useParallel'),   opts.useParallel = true; end
if ~isfield(opts,'verbose'),       opts.verbose = false; end
if ~isfield(opts,'rngSeed'),       opts.rngSeed = []; end

groupLabels = groupLabels(:);
S = numel(groupLabels);

if ~isempty(opts.rngSeed)
    rng(opts.rngSeed);
end

% ------------------------------ observed statistics and clusters
statsObs = compute_edgewise_group_stat(W, groupLabels, opts);
clustersObs = build_node_frequency_clusters_fn( ...
    statsObs.Tef, statsObs.iUT, statsObs.jUT, statsObs.nNodes, ...
    opts.t0, opts.tail, opts.clusterMetric);

if opts.verbose
    if isempty(clustersObs)
        fprintf('Observed | clusters=0 | maxExtent=0 | maxMass=0 | metric=%s\n', ...
            opts.clusterMetric);
    else
        fprintf('Observed | clusters=%d | maxExtent=%.6g | maxMass=%.6g | metric=%s | maxStat=%.6g\n', ...
            numel(clustersObs), ...
            max([clustersObs.extent]), ...
            max([clustersObs.mass]), ...
            opts.clusterMetric, ...
            max([clustersObs.testStat]));
    end
end

% ------------------------------ permutation setup
nullMaxCluster = zeros(opts.nPerm,1);

switch lower(opts.test)
    case {'two-sample','twosample','independent','between'}
        permMat = zeros(S, opts.nPerm);
        for p = 1:opts.nPerm
            permMat(:,p) = randperm(S);
        end

    case {'paired','within','dependent'}
        error(['Paired permutation not yet implemented in node_frequency_permutation. ' ...
               'Use two-sample designs for now, or extend with sign-flipping.']);

    otherwise
        error('Unsupported opts.test: %s', opts.test);
end

% ------------------------------ permutation null
if opts.useParallel
    parfor p = 1:opts.nPerm
        permLabels = groupLabels(permMat(:,p));

        statsPerm = compute_edgewise_group_stat(W, permLabels, opts);
        clustersPerm = build_node_frequency_clusters_fn( ...
            statsPerm.Tef, statsPerm.iUT, statsPerm.jUT, statsPerm.nNodes, ...
            opts.t0, opts.tail, opts.clusterMetric);

        if isempty(clustersPerm)
            nullMaxCluster(p) = 0;
        else
            nullMaxCluster(p) = max([clustersPerm.testStat]);
        end
    end
else
    for p = 1:opts.nPerm
        permLabels = groupLabels(permMat(:,p));

        statsPerm = compute_edgewise_group_stat(W, permLabels, opts);
        clustersPerm = build_node_frequency_clusters_fn( ...
            statsPerm.Tef, statsPerm.iUT, statsPerm.jUT, statsPerm.nNodes, ...
            opts.t0, opts.tail, opts.clusterMetric);

        if isempty(clustersPerm)
            nullMaxCluster(p) = 0;
            nClust = 0;
        else
            nullMaxCluster(p) = max([clustersPerm.testStat]);
            nClust = numel(clustersPerm);
        end

        if opts.verbose
            fprintf('Perm %d/%d | clusters=%d | metric=%s | maxStat=%.6g\n', ...
                p, opts.nPerm, nClust, opts.clusterMetric, nullMaxCluster(p));
        end
    end
end
end