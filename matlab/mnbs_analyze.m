function result = mnbs_analyze(W, design, opts)
%MNBS_ANALYZE Network-based statistic for a stack of networks (Multiplex-NBS).
%
%   result = mnbs_analyze(W, group)
%   result = mnbs_analyze(W, group, opts)
%   result = mnbs_analyze(W, model, opts)
%
%   Tests an effect at every edge in every layer, keeps the edges whose
%   statistic exceeds a primary threshold, joins them into connected
%   components of region-layer sites, and gives each component a family-wise
%   corrected p-value from the permutation distribution of the largest
%   component. Layers are successive time points, frequency bins or another
%   ordered measurement of the same network.
%
%   Inputs
%     W      Connectivity. A cell array with one N-by-N-by-L matrix per
%            observation (N regions, L layers), or a numeric S-by-N-by-N-by-L
%            array (S observations). Matrices must be real, finite and
%            symmetric, with the same regions in the same order throughout.
%     group  Numeric vector with one entry per observation:
%            - two group labels (default): Welch t, first sorted label minus
%              the second; or
%            - pair IDs, each appearing twice, with opts.test = 'paired': the
%              first observation of each pair minus the second.
%     model  A GLM instead of group: struct with fields
%              .X         S-by-p design matrix (include an intercept column)
%              .C         contrast, 1-by-p for a t test or k-by-p for an F test
%              .statType  't' or 'F'
%     opts   Optional struct with any of these fields (default in brackets):
%              .t0             primary threshold                          [3]
%              .tail           'right', 'left' or 'both'                  ['right']
%              .clusterMetric  'extent' (region-layer sites) or 'mass'    ['extent']
%              .layerAdjacency 'consecutive' = Multiplex-NBS              ['consecutive']
%                              'independent' = Layer-wise NBS (components
%                              stay in their layer; one correction for all)
%              .nPerm          random permutations; use >= 5000 to report [1000]
%              .rngSeed        random seed                                [1]
%              .alpha          reporting cutoff for result.significant    [0.05]
%              .test           'two-sample' or 'paired'                   ['two-sample']
%              .pairs          nPairs-by-2 observation indices (paired)   []
%              .method         GLM resampling: 'auto' (Freedman-Lane),
%                              'freedman-lane' or 'rowshuffle'            ['auto']
%              .exchangeBlocks S-by-1 labels; permute only within blocks  []
%              .axisName, .axisUnit, .axisValues   label the layers,
%                              e.g. 'Frequency', 'Hz', 4:2:18             ['Layer','',1:L]
%              .freqMask       layers to analyse (logical or indices)     [all]
%              .useAbs         use absolute connectivity values           [false]
%              .useParallel    permutations in parfor (Parallel Toolbox)  [false]
%              .progress       function handle, progress(done, total)     []
%              .verbose        print a summary                            [false]
%
%   Output
%     result  struct with fields
%       .clusters     one element per observed component, with .nodes
%                     (regions), .layerBins (layers), .extent, .mass, .tail,
%                     .p_FWE and .nodeFreqIdx (sites)
%       .pvalues      corrected p-value of each component
%       .significant  table of components with p_FWE <= opts.alpha (id,
%                     nNodes, nFreqBins, freqMin, freqMax as layer indices,
%                     extent, mass, testStat, p_FWE, nodeList)
%       .report       summary (counts, null distribution percentiles)
%       .nullMax      largest component in each permutation
%       .stats        edge statistics (.Tef, edges-by-layers) and edge list
%       .axis, .options, .design, .method, .version
%
%   The corrected p-value applies to a component as a whole, not to any of
%   its edges, regions or layers, and the first and last layers it spans are
%   not corrected estimates of where an effect starts or stops. Classic NBS
%   on a single network is available in the Python package (classic_nbs) and
%   the desktop app; see docs/classic-nbs-parity.md.
%
%   Example
%     d = mnbs_load_demo('brain-network');
%     opts = struct('t0', 3, 'nPerm', 999, 'axisName', d.axisName, ...
%                   'axisUnit', d.axisUnit, 'axisValues', d.axisValues);
%     result = mnbs_analyze(d.W, d.group, opts);
%     disp(result.significant)
%
%   See also MNBS_LOAD_DEMO, MNBS_GUI, MNBS_EDGESTAT_GROUP, MNBS_EDGESTAT_GLM,
%   MNBS_COMPONENTS, MNBS_PERMUTE, MNBS_PERMUTE_GLM, MNBS_SUMMARIZE.
%
%   Reference: Zalesky A, Fornito A, Bullmore ET (2010). Network-based
%   statistic: identifying differences in brain networks. NeuroImage 53:1197-1207.
%
%   Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
%   https://github.com/Minarose/multiplex-nbs

if nargin<3, opts=struct(); end
if ~isstruct(opts) || ~isscalar(opts), error('opts must be a scalar struct.'); end
defaults=struct('nPerm',1000,'t0',3,'tail','right','clusterMetric','extent', ...
    'rngSeed',1,'test','two-sample','useParallel',false,'verbose',false, ...
    'alpha',0.05,'freqMask',[],'useAbs',false,'exchangeBlocks',[], ...
    'method','auto','pairs',[],'progress',[], ...
    'axisName','Layer','axisUnit','','axisValues',[],'layerAdjacency','consecutive');
names=fieldnames(opts);
for k=1:numel(names)
    if ~isfield(defaults,names{k}), error('Unknown option: %s',names{k}); end
end
names=fieldnames(defaults);
for k=1:numel(names)
    if ~isfield(opts,names{k}), opts.(names{k})=defaults.(names{k}); end
end
validateattributes(opts.nPerm,{'numeric'},{'scalar','integer','positive','finite'});
validateattributes(opts.t0,{'numeric'},{'scalar','positive','finite','real'});
validateattributes(opts.rngSeed,{'numeric'},{'scalar','integer','nonnegative','<=',2^32-1});
validateattributes(opts.alpha,{'numeric'},{'scalar','>',0,'<',1,'finite'});
opts.layerAdjacency=validatestring(opts.layerAdjacency,{'consecutive','independent'});
for field={'axisName','axisUnit'}
    key=field{1}; value=opts.(key);
    if isstring(value) && isscalar(value) && ~ismissing(value)
        value=char(value);
    elseif ~ischar(value) || (~isempty(value) && ~isrow(value))
        error('%s must be a scalar text label.',key);
    end
    opts.(key)=strtrim(value);
end
if isempty(opts.axisName), error('axisName must be a nonempty text label.'); end
opts.tail=validatestring(opts.tail,{'right','left','both'});
opts.clusterMetric=validatestring(opts.clusterMetric,{'extent','mass'});
opts.test=validatestring(opts.test,{'two-sample','paired'});
opts.method=validatestring(opts.method,{'auto','freedman-lane','rowshuffle'});
if ~isempty(opts.progress) && ~isa(opts.progress,'function_handle'), error('progress must be a function handle.'); end
validateattributes(opts.useAbs,{'logical','numeric'},{'scalar','binary'});
validateattributes(opts.useParallel,{'logical','numeric'},{'scalar','binary'});
if isnumeric(W)
    if ndims(W)<3 || ndims(W)>4 || size(W,2)~=size(W,3)
        error('Numeric W must be S-by-N-by-N-by-F. Use cells for N-by-N-by-F subjects.');
    end
    data=W; W=cell(size(data,1),1);
    for s=1:numel(W), W{s}=reshape(data(s,:,:,:),size(data,2),size(data,3),size(data,4)); end
end
if ~iscell(W) || isempty(W), error('W must contain observation connectivity matrices.'); end
S=numel(W); N=size(W{1},1); F=size(W{1},3);
if N<2, error('At least two nodes are required.'); end
if isempty(opts.axisValues), opts.axisValues=1:F; end
validateattributes(opts.axisValues,{'numeric'},{'vector','numel',F,'finite','real'});
if any(diff(opts.axisValues(:))<=0), error('axisValues must be strictly increasing.'); end
for s=1:S
    M=W{s};
    if ~isnumeric(M) || ~isreal(M) || ndims(M)>3 || size(M,1)~=N || size(M,2)~=N || size(M,3)~=F
        error('Every W cell must be a real N-by-N-by-F matrix of the same size.');
    end
    if any(~isfinite(M(:))), error('W contains missing or infinite values. Supply complete finite data.'); end
    M=double(M);
    mirrored=permute(M,[2 1 3]);
    difference=abs(M-mirrored); tolerance=1e-10+1e-7*abs(mirrored);
    if any(difference(:)>tolerance(:))
        error('W must be symmetric; directed networks are unsupported.');
    end
    W{s}=double(M);
end
bins=opts.freqMask;
if islogical(bins)
    if numel(bins)~=F, error('Logical freqMask must contain F elements.'); end
    bins=find(bins);
end
if ~isempty(bins)
    validateattributes(bins,{'numeric'},{'vector','integer','>=',1,'<=',F});
    if any(diff(bins(:))<=0), error('Select distinct layers in increasing order.'); end
    if strcmp(opts.layerAdjacency,'consecutive') && any(diff(bins(:))~=1)
        error('Consecutive adjacency requires contiguous layers; use independent adjacency for separated layers.');
    end
elseif ~isempty(opts.freqMask)
    error('freqMask selects no frequency bins.');
end
opts.freqMask=bins;
if ~isempty(opts.exchangeBlocks)
    validateattributes(opts.exchangeBlocks,{'numeric'},{'vector','numel',S,'finite','real'});
    opts.exchangeBlocks=opts.exchangeBlocks(:);
end
blockLabels=opts.exchangeBlocks;
if isempty(blockLabels), blockLabels=ones(S,1); end
blockIDs=unique(blockLabels);
previousRng=rng; restoreRng=onCleanup(@()rng(previousRng)); %#ok<NASGU>
if isstruct(design)
    required={'X','C','statType'};
    for k=1:numel(required)
        if ~isfield(design,required{k}), error('model.%s is required.',required{k}); end
    end
    X=design.X; C=design.C;
    validateattributes(X,{'numeric'},{'2d','real','finite','nonempty'});
    validateattributes(C,{'numeric'},{'2d','real','finite','nonempty'});
    X=double(X); C=double(C); design.X=X; design.C=C;
    if size(X,1)~=S || rank(X)~=size(X,2) || S<=size(X,2)
        error('Design needs one row per observation, full column rank and positive residual degrees of freedom.');
    end
    design.statType=validatestring(design.statType,{'t','F'});
    if strcmpi(design.statType,'t')
        if ~isvector(C), error('A t contrast must be one vector.'); end
        C=C(:)'; design.C=C;
    elseif ~strcmp(opts.tail,'right')
        error('F statistics require the right tail.');
    end
    if size(C,2)~=size(X,2) || rank(C)<size(C,1)
        error('Contrasts need independent nonzero rows and one column per design regressor.');
    end
    weights=(double(C)*pinv(double(X)))';
    weightScale=max(max(abs(weights(:))),realmin);
    canVary=false;
    for k=1:numel(blockIDs)
        within=weights(blockLabels==blockIDs(k),:);
        if any(max(within,[],1)-min(within,[],1)>1e-12*weightScale), canVary=true; end
    end
    if ~canVary
        error('The contrast cannot vary under allowed row shuffles. Use paired tests for paired differences.');
    end
    if ~isempty(opts.pairs) || strcmp(opts.test,'paired')
        error('For a GLM, use model and exchangeBlocks to specify repeated measures.');
    end
    perm=struct('method',opts.method,'nPerm',opts.nPerm,'rngSeed',opts.rngSeed, ...
        'useParallel',opts.useParallel,'exchangeBlocks',opts.exchangeBlocks);
    [clusters,nullMax,stats]=mnbs_permute_glm(W,design,perm,opts);
    method=stats.permutation.methodResolved;
else
    if ~strcmp(opts.method,'auto'), error('opts.method is a GLM option; use auto for independent/paired tests.'); end
    validateattributes(design,{'numeric'},{'vector','numel',S,'real','finite'});
    design=design(:);
    if strcmp(opts.test,'two-sample')
        labels=unique(design);
        if numel(labels)~=2 || any(arrayfun(@(g)sum(design==g)<2,labels))
            error('Use exactly two numeric group labels and at least two observations each.');
        end
        canVary=false;
        for k=1:numel(blockIDs)
            if numel(unique(design(blockLabels==blockIDs(k))))>1, canVary=true; end
        end
        if ~canVary, error('No group labels can exchange within the specified blocks.'); end
        if ~isempty(opts.pairs), error('opts.pairs is only used by a paired test.'); end
        method='label-shuffle';
    else
        if ~isempty(opts.exchangeBlocks), error('Paired swaps use pair IDs; omit exchangeBlocks.'); end
        if isempty(opts.pairs)
            labels=unique(design);
            if numel(labels)<2 || any(arrayfun(@(g)sum(design==g)~=2,labels))
                error('Use at least two pair IDs, each occurring exactly twice.');
            end
        else
            pairs=opts.pairs;
            validateattributes(pairs,{'numeric'},{'2d','integer','>=',1,'<=',S});
            if size(pairs,2)~=2 || size(pairs,1)<2 || numel(unique(pairs))~=numel(pairs) || numel(pairs)~=S
                error('opts.pairs must assign every observation once in an nPairs-by-2 matrix.');
            end
        end
        method='paired-swaps';
    end
    [clusters,nullMax,stats]=mnbs_permute(W,design,opts);
end
summaryOptions=struct('alpha',opts.alpha,'usePlusOne',true,'verbose',opts.verbose);
[pvalues,significant,report]=mnbs_summarize(clusters,nullMax,summaryOptions);
for k=1:numel(clusters), clusters(k).p_FWE=pvalues(k); end
opts.progress=[]; % Do not serialize a GUI callback into saved analysis options.
result=struct('clusters',clusters,'pvalues',pvalues,'significant',significant, ...
    'report',report,'nullMax',nullMax,'stats',stats,'options',opts, ...
    'design',design,'method',method,'version','0.1.0');
axisValues=opts.axisValues;
if ~isempty(opts.freqMask), axisValues=axisValues(opts.freqMask); end
result.axis=struct('name',char(opts.axisName),'unit',char(opts.axisUnit), ...
    'values',axisValues,'adjacency',opts.layerAdjacency);
end
