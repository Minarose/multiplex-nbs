function [clustersObs, nullMaxCluster, statsObs] = mnbs_permute(W, groupLabels, opts)
%MNBS_PERMUTE Permutation null for two-sample and paired designs.
%
%   [clustersObs, nullMax, statsObs] = mnbs_permute(W, groupLabels, opts)
%
%   Computes the observed edge statistics and components, then repeats the
%   component search after shuffling group labels (two-sample) or swapping
%   conditions within pairs (paired), recording the largest component of
%   each permutation. MNBS_ANALYZE calls this after validating inputs; call
%   it directly only to build a custom pipeline.
%
%   Inputs
%     W            S-by-1 cell of N-by-N-by-L matrices
%     groupLabels  S-by-1 group labels or pair IDs
%     opts         struct: .t0 (required), .nPerm, .rngSeed, .tail,
%                  .clusterMetric, .layerAdjacency, .test ('two-sample' or
%                  'paired'), .pairs, .exchangeBlocks, .useParallel, .progress
%
%   Outputs
%     clustersObs  observed components (see MNBS_COMPONENTS)
%     nullMax      nPerm-by-1 largest component statistic per permutation
%     statsObs     observed edge statistics (see MNBS_EDGESTAT_GROUP)
%
%   See also MNBS_ANALYZE, MNBS_PERMUTE_GLM, MNBS_SUMMARIZE.
%
%   Original implementation: Darren S. Kadis (March 2026).
%   Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
%   https://github.com/Minarose/multiplex-nbs
if nargin < 3, opts = struct(); end
defaults = struct('nPerm',1000,'tail','right','test','two-sample', ...
    'clusterMetric','extent','useParallel',false,'verbose',false, ...
    'rngSeed',1,'exchangeBlocks',[],'pairs',[],'layerAdjacency','consecutive');
names = fieldnames(defaults);
for k=1:numel(names)
    if ~isfield(opts,names{k}), opts.(names{k})=defaults.(names{k}); end
end
if ~isfield(opts,'t0'), error('opts.t0 is required.'); end
if ~isempty(opts.rngSeed), rng(opts.rngSeed,'twister'); end
groupLabels=groupLabels(:);
S=numel(groupLabels);
isPaired=ismember(lower(opts.test),{'paired','within','dependent'});
statsObs=mnbs_edgestat_group(W,groupLabels,opts);
clustersObs=mnbs_components(statsObs.Tef,statsObs.iUT, ...
    statsObs.jUT,statsObs.nNodes,opts.t0,opts.tail,opts.clusterMetric,opts.layerAdjacency);
permMat=zeros(S,opts.nPerm);
if isPaired
    pairs=opts.pairs;
    if isempty(pairs)
        ids=unique(groupLabels);
        pairs=zeros(numel(ids),2);
        for k=1:numel(ids)
            rows=find(groupLabels==ids(k));
            if numel(rows)~=2, error('Every pair ID must occur twice.'); end
            pairs(k,:)=rows';
        end
    end
    for p=1:opts.nPerm
        index=(1:S)';
        swap=pairs(rand(size(pairs,1),1)<0.5,:);
        index(swap(:,1))=swap(:,2); index(swap(:,2))=swap(:,1);
        permMat(:,p)=index;
    end
else
    blocks=opts.exchangeBlocks;
    if isempty(blocks), blocks=ones(S,1); end
    ids=unique(blocks(:));
    for p=1:opts.nPerm
        index=(1:S)';
        for k=1:numel(ids)
            rows=find(blocks==ids(k));
            index(rows)=rows(randperm(numel(rows)));
        end
        permMat(:,p)=index;
    end
end
nullMaxCluster=zeros(opts.nPerm,1);
if opts.useParallel
    parfor p=1:opts.nPerm
        nullMaxCluster(p)=local_max(W,groupLabels,permMat(:,p),opts,isPaired);
    end
else
    for p=1:opts.nPerm
        nullMaxCluster(p)=local_max(W,groupLabels,permMat(:,p),opts,isPaired);
        if isfield(opts,'progress') && ~isempty(opts.progress), opts.progress(p,opts.nPerm); end
        if opts.verbose && (p==1 || mod(p,100)==0 || p==opts.nPerm)
            fprintf('Permutation %d/%d\n',p,opts.nPerm);
        end
    end
end
end

function value=local_max(W,group,index,opts,isPaired)
if isPaired
    stats=mnbs_edgestat_group(W(index),group,opts);
else
    stats=mnbs_edgestat_group(W,group(index),opts);
end
clusters=mnbs_components(stats.Tef,stats.iUT,stats.jUT, ...
    stats.nNodes,opts.t0,opts.tail,opts.clusterMetric,opts.layerAdjacency);
value=0;
if ~isempty(clusters), value=max([clusters.testStat]); end
end
