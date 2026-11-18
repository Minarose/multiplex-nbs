function stats = mnbs_edgestat_glm(W, model, opts)
%MNBS_EDGESTAT_GLM Edge-by-layer GLM t or F statistics.
%
%   stats = mnbs_edgestat_glm(W, model)
%   stats = mnbs_edgestat_glm(W, model, opts)
%
%   Fits the design at every upper-triangle edge and layer and returns the
%   contrast statistic. No permutation is done.
%
%   Inputs
%     W      S-by-1 cell of N-by-N-by-L matrices
%     model  struct: .X (S-by-p, include an intercept), .C (1-by-p for t,
%            k-by-p for F), .statType ('t' or 'F')
%     opts   struct: .freqMask, .useAbs, .nanPolicy, .tail (t p-values only)
%
%   Output
%     stats  struct: .Tef (edges-by-layers t or F; the field name is kept for
%            compatibility), .Pef, degrees of freedom, maps and edge indices
%
%   See also MNBS_EDGESTAT_GROUP, MNBS_PERMUTE_GLM, MNBS_ANALYZE.
%
%   Original implementation: Darren S. Kadis (March 2026).
%   Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
%   https://github.com/Minarose/multiplex-nbs

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
    error('Design matrix is rank deficient: rank(X) = %d < %d columns.', rankX, p);
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
    Pmap(:,:,k)  = triu(Pf,1) + triu(Pf,1).' + eye(nNodes);
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

    inverse = pinv(Xk);
    beta = inverse * yk;
    contrastFit = C * inverse;
    contrastCovariance = contrastFit * contrastFit';
    res = yk - Xk * beta;
    df = size(Xk,1) - rk;

    if df <= 0
        continue
    end

    tolerance = 64 * eps * max(norm(yk), realmin);
    exactFit = norm(res) <= tolerance;
    if exactFit
        if any(abs(C*beta) > tolerance * vecnorm(contrastFit,2,2))
            error('A nonzero contrast has zero residual variance; inference is undefined.');
        end
        res(:) = 0;
    end
    s2 = sum(res.^2) / df;

    switch statType
        case "t"
            c = C(:)';
            denomConst = contrastCovariance(1,1);

            if denomConst <= 0 || s2 < 0
                stat = NaN;
                pval = NaN;
            else
                den = sqrt(s2 * denomConst);
                if exactFit
                    stat = 0;
                    pval = 1;
                else
                    stat = (c * beta) / den;
                    pval = local_ttail_to_p(stat, df, opts.tail);
                end
            end

        case "f"
            q = rank(C);
            M = contrastCovariance \ eye(size(C,1));
            cb = C * beta;

            if exactFit
                % The zero-error/nonzero-effect case was rejected above.
                stat = 0;
                pval = 1;
            else
                numer = (cb' * M * cb) / q;
                stat = max(numer / s2, 0);
                pval = betainc(df/(df + q*stat), df/2, q/2);
            end

        otherwise
            error('Unsupported statType: %s', statType);
    end

    if ~isfinite(stat), error('GLM statistics overflowed; check data scaling.'); end
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
if ndims(W{1}) > 3 || sz(1) ~= sz(2)
    error('Each W{s} must be an N x N x F matrix.');
end

nNodes = sz(1);
nFreq = size(W{1},3);

for s = 1:numel(W)
    if size(W{s},1) ~= nNodes || size(W{s},2) ~= nNodes || size(W{s},3) ~= nFreq || ndims(W{s}) > 3
        error('All W{s} matrices must have the same size N x N x F.');
    end
end
end

% ========================================================================
function p = local_ttail_to_p(t, df, tail)
switch lower(tail)
    case {'both','two','two-sided','twosided'}
        p = 2 * mnbs_tcdf(-abs(t), df);
    case {'right','greater'}
        p = mnbs_tcdf(-t, df);
    case {'left','less'}
        p = mnbs_tcdf(t, df);
    otherwise
        error('Unsupported tail option: %s', tail);
end
end