function clusters = mnbs_components(Tef, iUT, jUT, nNodes, t0, tail, clusterMetric, layerAdjacency)
%MNBS_COMPONENTS Connected components of region-layer sites.
%
%   clusters = mnbs_components(Tef, iUT, jUT, nNodes, t0)
%   clusters = mnbs_components(Tef, iUT, jUT, nNodes, t0, tail, clusterMetric, layerAdjacency)
%
%   Keeps edges whose statistic exceeds the threshold t0. A kept edge joins
%   its two regions within a layer; with 'consecutive' adjacency a region
%   active in two neighbouring layers is also joined to itself. No inference
%   is done here.
%
%   Inputs
%     Tef             edges-by-layers statistic map
%     iUT, jUT        endpoints of each edge (upper triangle, 1-based)
%     nNodes          number of regions
%     t0              primary threshold
%     tail            'right', 'left' or 'both' (signs kept separate)  ['right']
%     clusterMetric   'extent' (number of sites), 'mass' or 'intensity' ['extent']
%                     (mass sums the edge statistics; intensity sums each
%                     minus t0, as in the NBS toolbox)
%     layerAdjacency  'consecutive' or 'independent'                   ['consecutive']
%
%   Output
%     clusters  struct array: .nodes, .layerBins (also .freqBins), .extent,
%               .mass, .intensity, .testStat (the chosen metric), .tail,
%               .nodeFreqIdx (sites), .nodeMask and .nodeMass
%
%   See also MNBS_EDGESTAT_GROUP, MNBS_PERMUTE, MNBS_ANALYZE.
%
%   Original implementation: Darren S. Kadis (March 2026).
%   Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
%   https://github.com/Minarose/multiplex-nbs

if nargin < 7 || isempty(clusterMetric)
    clusterMetric = 'extent';
end

if nargin < 8 || isempty(layerAdjacency), layerAdjacency='consecutive'; end
layerAdjacency=validatestring(layerAdjacency,{'consecutive','independent'});

% Two-sided inference keeps signs separate, then takes one maximum over both.
if strcmpi(tail,'both')
    pos = mnbs_components(Tef,iUT,jUT,nNodes,t0,'right',clusterMetric,layerAdjacency);
    neg = mnbs_components(Tef,iUT,jUT,nNodes,t0,'left',clusterMetric,layerAdjacency);
    if isempty(pos), clusters=neg;
    elseif isempty(neg), clusters=pos;
    else, clusters=[pos neg]; end
    for c = 1:numel(clusters), clusters(c).id = c; end
    return
end
validateattributes(t0, {'numeric'}, {'scalar','real','finite','positive'});
if ~ismember(lower(clusterMetric), {'extent','mass','intensity'})
    error('clusterMetric must be extent, mass or intensity.');
end
if any(~isfinite(Tef(:))), error('Statistic map must be finite.'); end

% ------------------------------ threshold edge map
[~, nFreq] = size(Tef);

switch lower(tail)
    case 'right'
        supraEdge = Tef > t0;
        Teff = Tef;
    case 'left'
        supraEdge = Tef < -t0;
        Teff = -Tef;
    otherwise
        error('Unknown tail: %s', tail);
end

% ------------------------------ accumulate node mask and node mass
nodeMask = false(nNodes, nFreq);
nodeMass = zeros(nNodes, nFreq);

for f = 1:nFreq
    ef = find(supraEdge(:,f));
    for k = 1:numel(ef)
        e = ef(k);
        i = iUT(e);
        j = jUT(e);
        w = Teff(e,f);

        nodeMask(i,f) = true;
        nodeMask(j,f) = true;

        % split edge contribution equally across endpoints
        nodeMass(i,f) = nodeMass(i,f) + w/2;
        nodeMass(j,f) = nodeMass(j,f) + w/2;
    end
end

% ------------------------------ build node-frequency adjacency
nSites = nNodes * nFreq;
ii = [];
jj = [];

% within-frequency links: endpoints of suprathreshold edges
for f = 1:nFreq
    ef = find(supraEdge(:,f));
    for k = 1:numel(ef)
        e = ef(k);
        a = sub2ind([nNodes, nFreq], iUT(e), f);
        b = sub2ind([nNodes, nFreq], jUT(e), f);
        ii(end+1,1) = a; %#ok<AGROW>
        jj(end+1,1) = b; %#ok<AGROW>
    end
end

% across-frequency links: same node in adjacent bins
lastLink=nFreq-1;
if strcmp(layerAdjacency,'independent'), lastLink=0; end
for f = 1:lastLink
    shared = find(nodeMask(:,f) & nodeMask(:,f+1));
    for k = 1:numel(shared)
        a = sub2ind([nNodes, nFreq], shared(k), f);
        b = sub2ind([nNodes, nFreq], shared(k), f+1);
        ii(end+1,1) = a; %#ok<AGROW>
        jj(end+1,1) = b; %#ok<AGROW>
    end
end

% ------------------------------ restrict to active sites and find components
activeIdx = find(nodeMask(:));
if isempty(activeIdx)
    clusters = struct([]);
    return
end

A = sparse([ii; jj], [jj; ii], true, nSites, nSites);
A = A(activeIdx, activeIdx);
cc = conncomp(graph(A));

% Both endpoints of a kept edge share a component; label each edge by its first endpoint.
siteLabel = zeros(nSites, 1);
siteLabel(activeIdx) = cc;
[edgeRows, edgeLayers] = find(supraEdge);
edgeLabel = siteLabel(sub2ind([nNodes, nFreq], reshape(iUT(edgeRows), [], 1), edgeLayers(:)));

% ------------------------------ summarize clusters
nClust = max(cc);
clusters = repmat(local_empty_cluster(), 1, nClust);

for c = 1:nClust
    siteIdx = activeIdx(cc == c);
    [nodesC, freqsC] = ind2sub([nNodes, nFreq], siteIdx);

    maskC = false(nNodes, nFreq);
    maskC(siteIdx) = true;

    extentC = numel(siteIdx);
    massC   = sum(nodeMass(siteIdx), 'omitnan');
    if ~isfinite(massC), error('Cluster mass overflowed; check statistic scaling.'); end

    intensityC = massC - t0 * nnz(edgeLabel == c);

    switch lower(clusterMetric)
        case 'extent'
            testStatC = extentC;
        case 'mass'
            testStatC = massC;
        case 'intensity'
            testStatC = intensityC;
        otherwise
            error('Unknown clusterMetric: %s. Use ''extent'', ''mass'' or ''intensity''.', clusterMetric);
    end

    clusters(c).id            = c;
    clusters(c).tail          = lower(tail);
    clusters(c).nodeFreqIdx   = siteIdx(:);
    clusters(c).nodes         = unique(nodesC(:))';
    clusters(c).freqBins      = unique(freqsC(:))';
    clusters(c).layerBins     = clusters(c).freqBins;
    clusters(c).nNodes        = numel(clusters(c).nodes);
    clusters(c).nFreqBins     = numel(clusters(c).freqBins);
    clusters(c).siteCount     = extentC;   % retained for backward compatibility
    clusters(c).extent        = extentC;
    clusters(c).mass          = massC;
    clusters(c).intensity     = intensityC;
    clusters(c).clusterMetric = lower(clusterMetric);
    clusters(c).testStat      = testStatC;
    clusters(c).nodeMask      = maskC;
    clusters(c).nodeMass      = nodeMass .* maskC;
end
end

function s = local_empty_cluster()
s = struct( ...
    'id', [], ...
    'tail', '', ...
    'nodeFreqIdx', [], ...
    'nodes', [], ...
    'freqBins', [], ...
    'layerBins', [], ...
    'nNodes', 0, ...
    'nFreqBins', 0, ...
    'siteCount', 0, ...
    'extent', 0, ...
    'mass', 0, ...
    'intensity', 0, ...
    'clusterMetric', '', ...
    'testStat', 0, ...
    'nodeMask', [], ...
    'nodeMass', []);
end
