function stats = mnbs_edgestat_group(W, group, opts)
%MNBS_EDGESTAT_GROUP Edge-by-layer statistics for two groups or pairs.
%
%   stats = mnbs_edgestat_group(W, group)
%   stats = mnbs_edgestat_group(W, group, opts)
%
%   Welch t for two independent groups (first sorted label minus second) or
%   paired t (first observation of each pair minus second) at every
%   upper-triangle edge and layer. No permutation is done.
%
%   Inputs
%     W      S-by-1 cell of N-by-N-by-L matrices
%     group  S-by-1 group labels or pair IDs
%     opts   struct: .test ('two-sample' or 'paired'), .tail (for the
%            parametric p-values only), .freqMask, .useAbs, .nanPolicy, .pairs
%
%   Output
%     stats  struct: .Tef (edges-by-layers statistics), .Pef (uncorrected
%            p-values), .Dfef, .Tmap / .Pmap (N-by-N-by-L), .iUT / .jUT (edge
%            endpoints), group labels and sizes
%
%   The uncorrected p-values are descriptive; use MNBS_ANALYZE for inference.
%
%   See also MNBS_EDGESTAT_GLM, MNBS_COMPONENTS, MNBS_ANALYZE.
%
%   Original implementation: Darren S. Kadis (March 2026).
%   Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
%   https://github.com/Minarose/multiplex-nbs

% ------------------------------ defaults and checks
if nargin < 3, opts = struct(); end
if ~isfield(opts,'test'),      opts.test = 'two-sample'; end
if ~isfield(opts,'tail'),      opts.tail = 'both'; end
if ~isfield(opts,'freqMask'),  opts.freqMask = []; end
if ~isfield(opts,'useAbs'),    opts.useAbs = false; end
if ~isfield(opts,'nanPolicy'), opts.nanPolicy = 'omitnan'; end
if ~isfield(opts,'pairs'),     opts.pairs = []; end

if ~iscell(W) || isempty(W)
    error('W must be a non-empty cell array of N x N x F matrices.');
end

nSubj = numel(W);
group = group(:);
if numel(group) ~= nSubj
    error('group must contain one entry per subject.');
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

% ------------------------------ stack subject data: edge x frequency x subject
X = nan(nEdges, nFreqSel, nSubj);
for s = 1:nSubj
    Ws = W{s};
    if opts.useAbs, Ws = abs(Ws); end
    for k = 1:nFreqSel
        tmp = Ws(:,:,freqIdx(k));
        X(:,k,s) = tmp(utMask);
    end
end

% ------------------------------ edge-wise statistical testing
Tef  = nan(nEdges, nFreqSel);
Pef  = nan(nEdges, nFreqSel);
Dfef = nan(nEdges, nFreqSel);

switch lower(opts.test)
    case {'two-sample','twosample','independent','between'}
        ug = unique(group);
        if numel(ug) ~= 2
            error('Two-sample test requires exactly two unique group labels.');
        end

        idx1 = group == ug(1);
        idx2 = group == ug(2);

        if sum(idx1) < 2 || sum(idx2) < 2
            error('Each group must contain at least 2 subjects.');
        end

        for e = 1:nEdges
            for f = 1:nFreqSel
                x1 = squeeze(X(e,f,idx1));
                x2 = squeeze(X(e,f,idx2));
                [Tef(e,f), Pef(e,f), Dfef(e,f)] = local_ttest2_welch_scalar(x1, x2, opts.tail, opts.nanPolicy);
            end
        end

        groupValues = ug;
        group1Label = ug(1);
        group2Label = ug(2);

    case {'paired','within','dependent'}
        pairs = opts.pairs;
        if isempty(pairs)
            pairs = local_build_pairs_from_ids(group);
        end
        if size(pairs,2) ~= 2 || size(pairs,1) < 2
            error('Paired test requires an [nPairs x 2] index matrix with at least 2 pairs.');
        end

        for e = 1:nEdges
            for f = 1:nFreqSel
                x1 = squeeze(X(e,f,pairs(:,1)));
                x2 = squeeze(X(e,f,pairs(:,2)));
                [Tef(e,f), Pef(e,f), Dfef(e,f)] = local_ttest_paired_scalar(x1, x2, opts.tail, opts.nanPolicy);
            end
        end

        groupValues = [];
        group1Label = [];
        group2Label = [];

    otherwise
        error('Unsupported opts.test: %s', opts.test);
end

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
stats.Tef         = Tef;
stats.Pef         = Pef;
stats.Dfef        = Dfef;
stats.Tmap        = Tmap;
stats.Pmap        = Pmap;
stats.df          = DfMap;
stats.groupValues = groupValues;
stats.group1Label = group1Label;
stats.group2Label = group2Label;
stats.freqIdx     = freqIdx;
stats.nNodes      = nNodes;
stats.nEdges      = nEdges;
stats.nFreq       = nFreqSel;
stats.nSubj       = nSubj;
stats.iUT         = iUT;
stats.jUT         = jUT;
end

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

function [t, p, df] = local_ttest2_welch_scalar(x1, x2, tail, nanPolicy)
if strcmpi(nanPolicy,'omitnan')
    x1 = x1(~isnan(x1));
    x2 = x2(~isnan(x2));
end

n1 = numel(x1); n2 = numel(x2);
if n1 < 2 || n2 < 2
    t = NaN; p = NaN; df = NaN; return
end

m1 = mean(x1); m2 = mean(x2);
v1 = var(x1,0); v2 = var(x2,0);
se = sqrt(v1/n1 + v2/n2);

if se == 0
    if m1 ~= m2, error('A nonzero group difference has zero standard error; inference is undefined.'); end
    t = 0; p = 1; df = n1 + n2 - 2; return
end

t = (m1 - m2) / se;
df = (v1/n1 + v2/n2)^2 / ((v1/n1)^2/(n1-1) + (v2/n2)^2/(n2-1));
p = local_ttail_to_p(t, df, tail);
end

function [t, p, df] = local_ttest_paired_scalar(x1, x2, tail, nanPolicy)
d = x1 - x2;
if strcmpi(nanPolicy,'omitnan')
    d = d(~isnan(d));
end

n = numel(d);
if n < 2
    t = NaN; p = NaN; df = NaN; return
end

md = mean(d);
sd = std(d,0);
se = sd / sqrt(n);

if se == 0
    if md ~= 0, error('A nonzero paired difference has zero standard error; inference is undefined.'); end
    t = 0; p = 1; df = n - 1; return
end

t = md / se;
df = n - 1;
p = local_ttail_to_p(t, df, tail);
end

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

function pairs = local_build_pairs_from_ids(pairIDs)
u = unique(pairIDs);
pairs = zeros(numel(u),2);
for k = 1:numel(u)
    idx = find(pairIDs == u(k));
    if numel(idx) ~= 2
        error('Each pair ID must correspond to exactly two subjects.');
    end
    pairs(k,:) = idx(:)';
end
end