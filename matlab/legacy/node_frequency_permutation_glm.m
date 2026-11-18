function [clustersObs, nullMaxCluster, statsObs] = node_frequency_permutation_glm(W, model, permSpec, opts)
% NODE_FREQUENCY_PERMUTATION_GLM
% Darren S. Kadis, PhD | 25MAR2026 | Toronto, Canada
%
% Permutation wrapper for node-frequency clustering using a general GLM.
%
% Supported permutation methods
%   'auto'           : row-shuffle for simple exchangeable designs,
%                      Freedman-Lane otherwise
%   'rowshuffle'     : permute rows of the design matrix
%   'freedman-lane'  : residual permutation under the reduced model
%
% Inputs
%   W         : cell array of N x N x F connectivity matrices, one per subject
%
%   model     : struct with fields
%               .X              [nSubj x p] design matrix
%               .C              contrast vector/matrix
%               .statType       't' or 'F'
%               .regressorNames (optional)
%               .designName     (optional)
%
%   permSpec  : struct with fields
%               .method         'auto' (default), 'rowshuffle', 'freedman-lane'
%               .nPerm          number of permutations (default 1000)
%               .exchangeBlocks optional [nSubj x 1] block labels
%               .useParallel    true/false (default true)
%               .rngSeed        optional scalar seed
%
%   opts      : struct with fields
%               .t0             primary threshold (required)
%               .tail           'left','right','both' (default 'both')
%               .clusterMetric  'extent' (default) or 'mass'
%               .freqMask       optional frequency subset
%               .useAbs         false by default
%               .verbose        true/false (default true)
%
% Outputs
%   clustersObs     : observed node-frequency clusters
%   nullMaxCluster  : max cluster statistic over permutations
%   statsObs        : observed edgewise GLM statistics and metadata

% -------------------------------------------------------------------------
% defaults
if nargin < 4, opts = struct(); end
if nargin < 3, permSpec = struct(); end

if ~isfield(opts,'t0'),            error('opts.t0 is required.'); end
if ~isfield(opts,'tail'),          opts.tail = 'both'; end
if ~isfield(opts,'clusterMetric'), opts.clusterMetric = 'extent'; end
if ~isfield(opts,'freqMask'),      opts.freqMask = []; end
if ~isfield(opts,'useAbs'),        opts.useAbs = false; end
if ~isfield(opts,'verbose'),       opts.verbose = true; end

if ~isfield(permSpec,'method'),         permSpec.method = 'auto'; end
if ~isfield(permSpec,'nPerm'),          permSpec.nPerm = 1000; end
if ~isfield(permSpec,'exchangeBlocks'), permSpec.exchangeBlocks = []; end
if ~isfield(permSpec,'useParallel'),    permSpec.useParallel = true; end
if ~isfield(permSpec,'rngSeed'),        permSpec.rngSeed = []; end

% -------------------------------------------------------------------------
% validate model
reqFields = {'X','C','statType'};
for k = 1:numel(reqFields)
    if ~isfield(model, reqFields{k})
        error('model.%s is required.', reqFields{k});
    end
end

X = double(model.X);
C = double(model.C);
statType = lower(string(model.statType));

nSubj = numel(W);
if size(X,1) ~= nSubj
    error('model.X must have one row per subject.');
end

if ~isempty(permSpec.exchangeBlocks)
    exchangeBlocks = permSpec.exchangeBlocks(:);
    if numel(exchangeBlocks) ~= nSubj
        error('permSpec.exchangeBlocks must have one entry per subject.');
    end
else
    exchangeBlocks = [];
end

if ~isempty(permSpec.rngSeed)
    rng(permSpec.rngSeed);
end

% -------------------------------------------------------------------------
% resolve permutation method
permMethod = lower(string(permSpec.method));
if permMethod == "auto"
    if local_is_simple_exchangeable_design(X, C, statType, exchangeBlocks)
        permMethod = "rowshuffle";
    else
        permMethod = "freedman-lane";
    end
end

% -------------------------------------------------------------------------
% observed stats
statsObs = compute_edgewise_glm_stat(W, model, opts);

clustersObs = build_node_frequency_clusters_fn( ...
    statsObs.Tef, statsObs.iUT, statsObs.jUT, statsObs.nNodes, ...
    opts.t0, opts.tail, opts.clusterMetric);

if opts.verbose
    if isempty(clustersObs)
        fprintf('Observed GLM | clusters=0 | metric=%s | permMethod=%s\n', ...
            opts.clusterMetric, char(permMethod));
    else
        fprintf('Observed GLM | clusters=%d | metric=%s | permMethod=%s | maxStat=%.6g\n', ...
            numel(clustersObs), opts.clusterMetric, char(permMethod), max([clustersObs.testStat]));
    end
end

% -------------------------------------------------------------------------
% stack data once
[Ymat, nNodes, nFreqSel, iUT, jUT, freqIdx] = local_stack_upper_triangle(W, opts);
nEdges = numel(iUT);

if any(isnan(Ymat(:)))
    error(['This first-pass GLM permutation implementation does not support NaNs. ' ...
           'Please remove or impute NaNs before permutation testing.']);
end

permIdx = local_build_permutation_indices(nSubj, permSpec.nPerm, exchangeBlocks);
nullMaxCluster = zeros(permSpec.nPerm, 1);

% -------------------------------------------------------------------------
% method-specific execution
switch permMethod
    case "rowshuffle"
        nullMaxCluster = local_run_rowshuffle( ...
            Ymat, X, C, statType, permIdx, ...
            iUT, jUT, nNodes, nEdges, nFreqSel, ...
            opts, permSpec);

    case "freedman-lane"
        [Yhat0, R0] = local_freedman_lane_setup(Ymat, X, C);
        nullMaxCluster = local_run_freedman_lane( ...
            Yhat0, R0, X, C, statType, permIdx, ...
            iUT, jUT, nNodes, nEdges, nFreqSel, ...
            opts, permSpec);

    otherwise
        error('Unsupported permutation method: %s', char(permMethod));
end

% -------------------------------------------------------------------------
% annotate observed stats
statsObs.freqIdx = freqIdx;
statsObs.permutation = permSpec;
statsObs.permutation.methodResolved = char(permMethod);

end

% =========================================================================
function tf = local_is_simple_exchangeable_design(X, C, statType, exchangeBlocks)

if ~isempty(exchangeBlocks)
    tf = false;
    return
end

if statType ~= "t"
    tf = false;
    return
end

if size(X,2) ~= 2
    tf = false;
    return
end

if ~all(abs(X(:,1) - 1) < 1e-12)
    tf = false;
    return
end

g = X(:,2);
ug = unique(g);
if numel(ug) ~= 2 || ~all(ismember(ug, [0 1]))
    tf = false;
    return
end

c = C(:)';
tf = isequal(size(c), [1 2]) && ...
     (all(abs(c - [0 1]) < 1e-12) || all(abs(c - [0 -1]) < 1e-12));
end

% =========================================================================
function nullMaxCluster = local_run_rowshuffle( ...
    Ymat, X, C, statType, permIdx, ...
    iUT, jUT, nNodes, nEdges, nFreqSel, ...
    opts, permSpec)

nPerm = size(permIdx, 2);
nullMaxCluster = zeros(nPerm, 1);

if permSpec.useParallel
    parfor p = 1:nPerm
        Pidx = permIdx(:,p);
        Xperm = X(Pidx, :);

        TefPerm = local_glm_stat_from_Ymat(Ymat, Xperm, C, statType, opts.tail, nEdges, nFreqSel);

        clustersPerm = build_node_frequency_clusters_fn( ...
            TefPerm, iUT, jUT, nNodes, opts.t0, opts.tail, opts.clusterMetric);

        if isempty(clustersPerm)
            nullMaxCluster(p) = 0;
        else
            nullMaxCluster(p) = max([clustersPerm.testStat]);
        end
    end
else
    for p = 1:nPerm
        Pidx = permIdx(:,p);
        Xperm = X(Pidx, :);

        TefPerm = local_glm_stat_from_Ymat(Ymat, Xperm, C, statType, opts.tail, nEdges, nFreqSel);

        clustersPerm = build_node_frequency_clusters_fn( ...
            TefPerm, iUT, jUT, nNodes, opts.t0, opts.tail, opts.clusterMetric);

        if isempty(clustersPerm)
            nullMaxCluster(p) = 0;
            nClust = 0;
        else
            nullMaxCluster(p) = max([clustersPerm.testStat]);
            nClust = numel(clustersPerm);
        end

        if opts.verbose
            fprintf('Perm %d/%d | method=rowshuffle | clusters=%d | metric=%s | maxStat=%.6g\n', ...
                p, nPerm, nClust, opts.clusterMetric, nullMaxCluster(p));
        end
    end
end
end

% =========================================================================
function nullMaxCluster = local_run_freedman_lane( ...
    Yhat0, R0, X, C, statType, permIdx, ...
    iUT, jUT, nNodes, nEdges, nFreqSel, ...
    opts, permSpec)

nPerm = size(permIdx, 2);
nullMaxCluster = zeros(nPerm, 1);

if permSpec.useParallel
    parfor p = 1:nPerm
        Pidx = permIdx(:,p);
        Yperm = Yhat0 + R0(Pidx, :);

        TefPerm = local_glm_stat_from_Ymat(Yperm, X, C, statType, opts.tail, nEdges, nFreqSel);

        clustersPerm = build_node_frequency_clusters_fn( ...
            TefPerm, iUT, jUT, nNodes, opts.t0, opts.tail, opts.clusterMetric);

        if isempty(clustersPerm)
            nullMaxCluster(p) = 0;
        else
            nullMaxCluster(p) = max([clustersPerm.testStat]);
        end
    end
else
    for p = 1:nPerm
        Pidx = permIdx(:,p);
        Yperm = Yhat0 + R0(Pidx, :);

        TefPerm = local_glm_stat_from_Ymat(Yperm, X, C, statType, opts.tail, nEdges, nFreqSel);

        clustersPerm = build_node_frequency_clusters_fn( ...
            TefPerm, iUT, jUT, nNodes, opts.t0, opts.tail, opts.clusterMetric);

        if isempty(clustersPerm)
            nullMaxCluster(p) = 0;
            nClust = 0;
        else
            nullMaxCluster(p) = max([clustersPerm.testStat]);
            nClust = numel(clustersPerm);
        end

        if opts.verbose
            fprintf('Perm %d/%d | method=freedman-lane | clusters=%d | metric=%s | maxStat=%.6g\n', ...
                p, nPerm, nClust, opts.clusterMetric, nullMaxCluster(p));
        end
    end
end
end

% =========================================================================
function [Yhat0, R0] = local_freedman_lane_setup(Ymat, X, C)
% Build reduced model under H0: C * beta = 0

N = null(C);

if isempty(N)
    X0 = zeros(size(X,1), 0);
else
    X0 = X * N;
    X0 = local_remove_redundant_columns(X0);
end

if isempty(X0)
    Yhat0 = zeros(size(Ymat));
    R0 = Ymat;
else
    beta0 = X0 \ Ymat;
    Yhat0 = X0 * beta0;
    R0 = Ymat - Yhat0;
end
end

% =========================================================================
function Xr = local_remove_redundant_columns(X)
if isempty(X)
    Xr = X;
    return
end

[Q, R] = qr(X, 0);
d = abs(diag(R));
tol = max(size(X)) * eps(max(d) + eps);
keep = d > tol;

if any(keep)
    Xr = Q(:, keep);
else
    Xr = zeros(size(X,1), 0);
end
end

% =========================================================================
function [Ymat, nNodes, nFreqSel, iUT, jUT, freqIdx] = local_stack_upper_triangle(W, opts)

nSubj = numel(W);
sz = size(W{1});
if numel(sz) ~= 3 || sz(1) ~= sz(2)
    error('Each W{s} must be N x N x F.');
end

nNodes = sz(1);
nFreq = sz(3);

if isempty(opts.freqMask)
    freqIdx = 1:nFreq;
elseif islogical(opts.freqMask)
    if numel(opts.freqMask) ~= nFreq
        error('Logical freqMask must have length equal to number of frequencies.');
    end
    freqIdx = find(opts.freqMask);
else
    freqIdx = opts.freqMask(:)';
end

nFreqSel = numel(freqIdx);

utMask = triu(true(nNodes), 1);
[iUT, jUT] = find(utMask);
nEdges = numel(iUT);
nVars = nEdges * nFreqSel;

Ymat = zeros(nSubj, nVars);

for s = 1:nSubj
    Ws = W{s};
    if opts.useAbs
        Ws = abs(Ws);
    end

    col0 = 0;
    for f = 1:nFreqSel
        tmp = Ws(:,:,freqIdx(f));
        Ymat(s, col0 + (1:nEdges)) = tmp(utMask);
        col0 = col0 + nEdges;
    end
end
end

% =========================================================================
function Tef = local_glm_stat_from_Ymat(Ymat, X, C, statType, tail, nEdges, nFreqSel)

[nSubj, nVars] = size(Ymat);
p = size(X,2);
rX = rank(X);

if rX < p
    error('Design matrix is rank deficient in permutation fit.');
end

XtX_inv = pinv(X' * X);
B = X \ Ymat;
R = Ymat - X * B;
df = nSubj - rX;

if df <= 0
    error('Non-positive residual degrees of freedom.');
end

s2 = sum(R.^2, 1) / df;

switch statType
    case "t"
        c = C(:)';
        denomConst = c * XtX_inv * c';
        if denomConst <= 0
            error('Invalid t-contrast: c*(X''X)^-1*c'' <= 0.');
        end

        num = c * B;
        den = sqrt(s2 * denomConst);
        stat = num ./ den;
        stat(~isfinite(stat)) = 0;

        switch lower(tail)
            case {'right','left','both','two','two-sided','twosided'}
                % keep signed t-statistics
            otherwise
                error('Unsupported tail option: %s', tail);
        end

    case "f"
        q = rank(C);
        M = pinv(C * XtX_inv * C');
        CB = C * B;

        stat = zeros(1, nVars);
        for v = 1:nVars
            numer = (CB(:,v)' * M * CB(:,v)) / q;
            if s2(v) <= 0 || ~isfinite(numer)
                stat(v) = 0;
            else
                stat(v) = numer / s2(v);
            end
        end

    otherwise
        error('Unsupported statType: %s', char(statType));
end

Tef = reshape(stat, [nEdges, nFreqSel]);
end

% =========================================================================
function permIdx = local_build_permutation_indices(nSubj, nPerm, exchangeBlocks)

permIdx = zeros(nSubj, nPerm);

if isempty(exchangeBlocks)
    for p = 1:nPerm
        permIdx(:,p) = randperm(nSubj)';
    end
    return
end

blocks = unique(exchangeBlocks(:))';
for p = 1:nPerm
    idx = zeros(nSubj,1);
    for b = blocks
        ib = find(exchangeBlocks == b);
        idx(ib) = ib(randperm(numel(ib)));
    end
    permIdx(:,p) = idx;
end
end