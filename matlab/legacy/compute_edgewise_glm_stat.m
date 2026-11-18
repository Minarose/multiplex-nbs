function stats = compute_edgewise_glm_stat(W, model, opts)
% COMPUTE_EDGEWISE_GLM_STAT
% Darren S. Kadis, PhD | 25MAR2026 | Toronto, Canada
% Compute edge x frequency GLM statistics from subject connectivity matrices.
%
% Inputs
%   W      : cell array of N x N x F connectivity matrices, one per subject
%   model  : struct with fields
%            .X             [nSubj x p] design matrix
%            .C             contrast vector/matrix
%            .statType      't' or 'F'
%            .regressorNames (optional)
%            .designName     (optional)
%
%   opts   : optional settings
%            .freqMask      frequency subset (default = all)
%            .useAbs        apply abs() to each connectivity matrix (default = false)
%            .nanPolicy     'omitnan' or 'includenan' (default = 'omitnan')
%            .tail          'both','left','right' (used for p-values in t-tests)
%
% Outputs
%   stats  : struct containing edgewise statistics and metadata
%
% Notes
%   - For t-tests, model.C must be a single contrast vector.
%   - For F-tests, model.C must be a contrast matrix.
%   - The returned field name Tef is retained for compatibility with the
%     existing clustering code, even though it may contain F-statistics.

% ------------------------------ defaults
if nargin < 3, opts = struct(); end
if ~isfield(opts,'freqMask'),  opts.freqMask = []; end
if ~isfield(opts,'useAbs'),    opts.useAbs = false; end
if ~isfield(opts,'nanPolicy'), opts.nanPolicy = 'omitnan'; end
if ~isfield(opts,'tail'),      opts.tail = 'both'; end

% ------------------------------ validate inputs
if ~iscell(W) || isempty(W)
    error('W must be a non-empty cell array of N x N x F matrices.');
end
if ~isstruct(model)
    error('model must be a struct.');
end

reqFields = {'X','C','statType'};
for k = 1:numel(reqFields)
    if ~isfield(model, reqFields{k})
        error('model.%s is required.', reqFields{k});
    end
end

Xdesign = double(model.X);
C = double(model.C);
statType = lower(string(model.statType));

nSubj = numel(W);
if size(Xdesign,1) ~= nSubj
    error('model.X must have one row per subject.');
end

[nNodes, nFreq] = local_validate_subject_matrices(W);

% ------------------------------ frequency selection and edge indexing
if isempty(opts.freqMask)
    freqIdx = 1:nFreq;
elseif islogical(opts.freqMask)
    if numel(opts.freqMask) ~= nFreq
        error('Logical freqMask must have length F.');
    end
    freqIdx = find(opts.freqMask);
else
    freqIdx = opts.freqMask(:)';
end

if isempty(freqIdx)
    error('opts.freqMask selected no frequencies.');
end

nFreqSel = numel(freqIdx);
utMask = triu(true(nNodes),1);
[iUT,jUT] = find(utMask);
nEdges = numel(iUT);

% ------------------------------ stack subject data
% Y is nSubj x nVars, where vars are ordered as:
% [all edges at freq1, all edges at freq2, ..., all edges at freqF]
nVars = nEdges * nFreqSel;
Y = nan(nSubj, nVars);

for s = 1:nSubj
    Ws = W{s};
    if opts.useAbs
        Ws = abs(Ws);
    end

    col0 = 0;
    for f = 1:nFreqSel
        tmp = Ws(:,:,freqIdx(f));
        Y(s, col0 + (1:nEdges)) = tmp(utMask);
        col0 = col0 + nEdges;
    end
end

% ------------------------------ validate contrast specification
[nObs, p] = size(Xdesign); %#ok<ASGLU>
rankX = rank(Xdesign);

if rankX < p
    warning('Design matrix is rank deficient: rank(X) = %d < %d columns.', rankX, p);
end

switch statType
    case "t"
        C = C(:)';
        if size(C,2) ~= p
            error('For t-tests, model.C must have length equal to size(model.X,2).');
        end
        if all(C == 0)
            error('Contrast vector C cannot be all zeros.');
        end

    case "f"
        if size(C,2) ~= p
            error('For F-tests, model.C must have %d columns.', p);
        end
        if rank(C) == 0
            error('Contrast matrix C cannot be rank zero.');
        end

    otherwise
        error('Unsupported model.statType: %s. Use ''t'' or ''F''.', statType);
end

% ------------------------------ edgewise GLM fit
[Tef, Pef, Dfef, Bef] = local_glm_stat_from_Ymat(Y, Xdesign, C, statType, opts, nEdges, nFreqSel);

% ------------------------------ mirror back to N x N x F
Tmap  = zeros(nNodes, nNodes, nFreqSel);
Pmap  = ones(nNodes,  nNodes, nFreqSel);
DfMap = zeros(nNodes, nNodes, nFreqSel);

for k = 1:nFreqSel
    Tf = zeros(nNodes);
    Pf = ones(nNodes);
    Df = zeros(nNodes);

    Tf(utMask) = Tef(:,k);
    Pf(utMask) = Pef(:,k);
    Df(utMask) = Dfef(:,k);

    Tmap(:,:,k)  = Tf + Tf.';
    Pmap(:,:,k)  = Pf + tril(Pf.', -1);
    DfMap(:,:,k) = Df + Df.';
end

% ------------------------------ package outputs
stats = struct();
stats.Tef            = Tef;          % retained name for compatibility
stats.Pef            = Pef;
stats.Dfef           = Dfef;
stats.Bef            = Bef;
stats.Tmap           = Tmap;
stats.Pmap           = Pmap;
stats.df             = DfMap;

stats.freqIdx        = freqIdx;
stats.nNodes         = nNodes;
stats.nEdges         = nEdges;
stats.nFreq          = nFreqSel;
stats.nSubj          = nSubj;
stats.nVars          = nVars;

stats.iUT            = iUT;
stats.jUT            = jUT;

stats.X              = Xdesign;
stats.C              = C;
stats.statType       = char(statType);
stats.rankX          = rankX;

if isfield(model,'regressorNames')
    stats.regressorNames = model.regressorNames;
else
    stats.regressorNames = {};
end

if isfield(model,'designName')
    stats.designName = model.designName;
else
    stats.designName = '';
end
end

% ========================================================================
function [Tef, Pef, Dfef, Bef] = local_glm_stat_from_Ymat(Y, X, C, statType, opts, nEdges, nFreqSel)
% Y is nSubj x nVars

[nSubj, nVars] = size(Y);
p = size(X,2);

Tef  = nan(nEdges, nFreqSel);
Pef  = nan(nEdges, nFreqSel);
Dfef = nan(nEdges, nFreqSel);
Bef  = nan(nEdges, nFreqSel, p);

for v = 1:nVars
    y = Y(:,v);

    switch lower(opts.nanPolicy)
        case 'omitnan'
            keep = ~isnan(y) & all(~isnan(X), 2);
        case 'includenan'
            keep = all(~isnan(X), 2);
        otherwise
            error('Unsupported opts.nanPolicy: %s', opts.nanPolicy);
    end

    yk = y(keep);
    Xk = X(keep,:);

    if numel(yk) <= size(Xk,2)
        continue
    end

    rk = rank(Xk);
    if rk < size(Xk,2)
        continue
    end

    beta = Xk \ yk;
    res = yk - Xk * beta;
    df = size(Xk,1) - rk;

    if df <= 0
        continue
    end

    s2 = sum(res.^2) / df;
    XtX_inv = pinv(Xk' * Xk);

    switch statType
        case "t"
            c = C(:)';
            denomConst = c * XtX_inv * c';

            if denomConst <= 0 || s2 < 0
                stat = NaN;
                pval = NaN;
            else
                den = sqrt(s2 * denomConst);
                if den == 0
                    stat = 0;
                    pval = 1;
                else
                    stat = (c * beta) / den;
                    pval = local_ttail_to_p(stat, df, opts.tail);
                end
            end

        case "f"
            q = rank(C);
            M = pinv(C * XtX_inv * C');
            cb = C * beta;

            if s2 <= 0
                if all(cb == 0)
                    stat = 0;
                    pval = 1;
                else
                    stat = NaN;
                    pval = NaN;
                end
            else
                numer = (cb' * M * cb) / q;
                stat = numer / s2;
                pval = 1 - fcdf(stat, q, df);
            end

        otherwise
            error('Unsupported statType: %s', statType);
    end

    [e, f] = ind2sub([nEdges, nFreqSel], v);
    Tef(e,f) = stat;
    Pef(e,f) = pval;
    Dfef(e,f) = df;
    Bef(e,f,:) = beta;
end
end

% ========================================================================
function [nNodes, nFreq] = local_validate_subject_matrices(W)
sz = size(W{1});
if numel(sz) ~= 3 || sz(1) ~= sz(2)
    error('Each W{s} must be an N x N x F matrix.');
end

nNodes = sz(1);
nFreq = sz(3);

for s = 1:numel(W)
    if ~isequal(size(W{s}), [nNodes, nNodes, nFreq])
        error('All W{s} matrices must have the same size N x N x F.');
    end
end
end

% ========================================================================
function p = local_ttail_to_p(t, df, tail)
switch lower(tail)
    case {'both','two','two-sided','twosided'}
        p = 2 * tcdf(-abs(t), df);
    case {'right','greater'}
        p = 1 - tcdf(t, df);
    case {'left','less'}
        p = tcdf(t, df);
    otherwise
        error('Unsupported tail option: %s', tail);
end
end