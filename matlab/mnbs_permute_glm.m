function [clustersObs, nullMaxCluster, statsObs] = mnbs_permute_glm(W, model, permSpec, opts)
%MNBS_PERMUTE_GLM Permutation null for a general linear model.
%
%   [clustersObs, nullMax, statsObs] = mnbs_permute_glm(W, model, permSpec, opts)
%
%   Observed GLM edge statistics and components, then the largest component
%   under each permutation. MNBS_ANALYZE calls this after validating inputs.
%
%   Inputs
%     W         S-by-1 cell of N-by-N-by-L matrices
%     model     struct: .X (S-by-p), .C (1-by-p for t, k-by-p for F),
%               .statType ('t' or 'F'), optional .regressorNames, .designName
%     permSpec  struct: .method ('auto' = Freedman-Lane, 'freedman-lane',
%               'rowshuffle'), .nPerm, .exchangeBlocks, .useParallel, .rngSeed
%     opts      struct: .t0 (required), .tail, .clusterMetric,
%               .layerAdjacency, .freqMask, .useAbs, .progress
%
%   Outputs
%     clustersObs, nullMax, statsObs as in MNBS_PERMUTE.
%
%   Freedman-Lane permutes residuals of the reduced model and is generally
%   approximate when nuisance regressors are present; 'rowshuffle' permutes
%   whole design rows and is exact only if that matches the randomisation.
%
%   See also MNBS_ANALYZE, MNBS_EDGESTAT_GLM, MNBS_PERMUTE.
%
%   Original implementation: Darren S. Kadis (March 2026).
%   Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
%   https://github.com/Minarose/multiplex-nbs

% -------------------------------------------------------------------------
% defaults
if nargin < 4, opts = struct(); end
if nargin < 3, permSpec = struct(); end

if ~isfield(opts,'t0'),            error('opts.t0 is required.'); end
if ~isfield(opts,'tail'),          opts.tail = 'both'; end
if ~isfield(opts,'clusterMetric'), opts.clusterMetric = 'extent'; end
if ~isfield(opts,'freqMask'),      opts.freqMask = []; end
if ~isfield(opts,'useAbs'),        opts.useAbs = false; end
if ~isfield(opts,'layerAdjacency'), opts.layerAdjacency='consecutive'; end
if ~isfield(opts,'verbose'),       opts.verbose = true; end

if ~isfield(permSpec,'method'),         permSpec.method = 'auto'; end
if ~isfield(permSpec,'nPerm'),          permSpec.nPerm = 9999; end
if ~isfield(permSpec,'exchangeBlocks'), permSpec.exchangeBlocks = []; end
if ~isfield(permSpec,'useParallel'),    permSpec.useParallel = false; end
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
if statType == "t", C=C(:)'; model.C=C; end

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
    permMethod = "freedman-lane";
end

% -------------------------------------------------------------------------
% observed stats
statsObs = mnbs_edgestat_glm(W, model, opts);

clustersObs = mnbs_components( ...
    statsObs.Tef, statsObs.iUT, statsObs.jUT, statsObs.nNodes, ...
    opts.t0, opts.tail, opts.clusterMetric, opts.layerAdjacency);

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

if any(~isfinite(Ymat(:)))
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

        clustersPerm = mnbs_components( ...
            TefPerm, iUT, jUT, nNodes, opts.t0, opts.tail, opts.clusterMetric, opts.layerAdjacency);

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

        clustersPerm = mnbs_components( ...
            TefPerm, iUT, jUT, nNodes, opts.t0, opts.tail, opts.clusterMetric, opts.layerAdjacency);

        if isempty(clustersPerm)
            nullMaxCluster(p) = 0;
            nClust = 0;
        else
            nullMaxCluster(p) = max([clustersPerm.testStat]);
            nClust = numel(clustersPerm);
        end

        if isfield(opts,'progress') && ~isempty(opts.progress), opts.progress(p,nPerm); end
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

        clustersPerm = mnbs_components( ...
            TefPerm, iUT, jUT, nNodes, opts.t0, opts.tail, opts.clusterMetric, opts.layerAdjacency);

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

        clustersPerm = mnbs_components( ...
            TefPerm, iUT, jUT, nNodes, opts.t0, opts.tail, opts.clusterMetric, opts.layerAdjacency);

        if isempty(clustersPerm)
            nullMaxCluster(p) = 0;
            nClust = 0;
        else
            nullMaxCluster(p) = max([clustersPerm.testStat]);
            nClust = numel(clustersPerm);
        end

        if isfield(opts,'progress') && ~isempty(opts.progress), opts.progress(p,nPerm); end
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
if ndims(W{1}) > 3 || sz(1) ~= sz(2)
    error('Each W{s} must be N x N x F.');
end

nNodes = sz(1);
nFreq = size(W{1},3);

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

inverse = pinv(X);
contrastFit = C * inverse;
contrastCovariance = contrastFit * contrastFit';
B = inverse * Ymat;
R = Ymat - X * B;
df = nSubj - rX;

if df <= 0
    error('Non-positive residual degrees of freedom.');
end

tolerance = 64 * eps * max(vecnorm(Ymat), realmin);
exactFit = vecnorm(R) <= tolerance;
contrastNonzero = any(abs(C*B) > vecnorm(contrastFit,2,2) * tolerance, 1);
if any(exactFit & contrastNonzero)
    error('A permuted contrast has zero residual variance; inference is undefined.');
end
R(:,exactFit) = 0;
s2 = sum(R.^2, 1) / df;

switch statType
    case "t"
        c = C(:)';
        denomConst = contrastCovariance(1,1);
        if denomConst <= 0
            error('Invalid t-contrast: c*(X''X)^-1*c'' <= 0.');
        end

        num = c * B;
        den = sqrt(s2 * denomConst);
        stat = zeros(1,nVars);
        stat(~exactFit) = num(~exactFit) ./ den(~exactFit);

        switch lower(tail)
            case {'right','left','both','two','two-sided','twosided'}
                % keep signed t-statistics
            otherwise
                error('Unsupported tail option: %s', tail);
        end

    case "f"
        q = rank(C);
        M = contrastCovariance \ eye(size(C,1));
        CB = C * B;

        stat = zeros(1, nVars);
        for v = 1:nVars
            numer = (CB(:,v)' * M * CB(:,v)) / q;
            if exactFit(v)
                stat(v) = 0;
            else
                stat(v) = max(numer / s2(v), 0);
            end
        end

    otherwise
        error('Unsupported statType: %s', char(statType));
end

if any(~isfinite(stat)), error('Permuted GLM statistics overflowed; check data scaling.'); end
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