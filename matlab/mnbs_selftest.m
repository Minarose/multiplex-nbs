function mnbs_selftest()
%MNBS_SELFTEST Run the toolbox's regression checks.
%
%   mnbs_selftest()
%
%   Checks clustering, the t distribution, symmetry, deterministic
%   permutations, t^2 = F, input validation and a golden fixture shared with
%   the Python package. Run after adding the matlab folder to the path; an
%   error is raised if any check fails. No additional toolbox is required.
%
%   See also MNBS_ANALYZE.
%
%   Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
%   https://github.com/Minarose/multiplex-nbs
goldenCheck();
[i,j]=find(triu(true(3),1)); % edges (1,2), (1,3), (2,3)
T=[4 0;0 0;0 5];
C=mnbs_components(T,i,j,3,3,'right','mass');
assert(numel(C)==1 && C.extent==4 && abs(C.mass-9)<1e-12);
assert(isequal(C.nodes,[1 2 3]) && isequal(C.freqBins,[1 2]));
independent=mnbs_components(T,i,j,3,3,'right','mass','independent');
assert(numel(independent)==2 && all([independent.extent]==2));
assert(isequal(C.layerBins,C.freqBins));
C2=mnbs_components(-T,i,j,3,3,'left','extent');
assert(C2.testStat==4 && abs(C2.mass-9)<1e-12);
% Intensity subtracts the threshold once per kept edge: 9 - 2 edges x 3.
Ci=mnbs_components(T,i,j,3,3,'right','intensity');
assert(abs(Ci.intensity-3)<1e-12 && abs(Ci.testStat-3)<1e-12 && abs(C2.intensity-3)<1e-12);
C3=mnbs_components([4;-5;0],i,j,3,3,'both','extent');
assert(numel(C3)==2 && all([C3.extent]==2));
assert(numel(mnbs_components(T,i,j,3,3,'both','extent'))==1);
assert(isempty(mnbs_components(zeros(3,1),i,j,3,3,'right','extent')));
assert(abs(mnbs_tcdf(1,1)-0.75)<1e-12);
assert(abs(mnbs_tcdf(-1,1)-0.25)<1e-12);

[W,g]=mnbs_demo(7);
options=struct('nPerm',19,'rngSeed',11,'tail','both','t0',3);
a=mnbs_analyze(W,g,options); b=mnbs_analyze(W,g,options);
assert(isequal(a.nullMax,b.nullMax) && isequal(a.stats.Tef,b.stats.Tef));
timeOptions=options; timeOptions.axisName='Time'; timeOptions.axisUnit='ms'; timeOptions.axisValues=0:50:450; % one value per demo layer (10)
timeResult=mnbs_analyze(W,g,timeOptions);
assert(isequal(a.nullMax,timeResult.nullMax) && isequal(a.pvalues,timeResult.pvalues));
assert(strcmp(timeResult.axis.name,'Time'));
adjacencyCheck();
assert(all(a.pvalues>=1/20) && all(a.pvalues<=1));
assert(max(abs(a.stats.Pmap(:)-reshape(permute(a.stats.Pmap,[2 1 3]),[],1)))<1e-12);
assert(all(a.stats.Pmap(:)>=0 & a.stats.Pmap(:)<=1));

% Single-frequency matrices used to fail validation in the original source.
Wone=cellfun(@(M)M(:,:,1),W,'UniformOutput',false);
single=mnbs_analyze(Wone,g,struct('nPerm',3,'t0',3));
assert(single.stats.nFreq==1);

% The first occurrence minus the second occurrence defines each pair.
pairID=[(1:20)';(1:20)'];
pair=mnbs_analyze(W,pairID,struct('test','paired','nPerm',3,'tail','both'));
assert(strcmp(pair.method,'paired-swaps') && numel(pair.nullMax)==3);

X=[ones(numel(W),1),double(g==1)];
model=struct('X',X,'C',[0 1],'statType','t');
glm=mnbs_analyze(W,model,struct('nPerm',3,'tail','both'));
assert(strcmp(glm.method,'freedman-lane') && all(isfinite(glm.stats.Tef(:))));
model.statType='F';
f=mnbs_analyze(W,model,struct('nPerm',3,'tail','right'));
assert(max(abs(f.stats.Tef(:)-glm.stats.Tef(:).^2))<1e-8);

bad=W; bad{1}(1,2,1)=NaN;
assertThrows(@()mnbs_analyze(bad,g,struct('nPerm',1)));
assertThrows(@()mnbs_analyze(W,g,struct('nPerm',0)));
assertThrows(@()mnbs_analyze(W,g,struct('nPerm',1,'freqMask',[1 3])));
assertThrows(@()mnbs_analyze(W,g,struct('nPerm',1,'axisName',' ')));
assertThrows(@()mnbs_analyze(W,g,struct('nPerm',1,'axisUnit',char('ms','Hz'))));
subset=mnbs_analyze(W,g,struct('nPerm',1,'freqMask',[1 3],'layerAdjacency','independent'));
assert(isequal(subset.axis.values,[1 3]));
assertThrows(@()mnbs_analyze(W,model,struct('nPerm',1,'tail','left')));
assertThrows(@()mnbs_analyze(W,g,struct('nPerm',1,'exchangeBlocks',g)));
model.X(:,2)=1;
assertThrows(@()mnbs_analyze(W,model,struct('nPerm',1)));
fprintf('Multiplex-NBS MATLAB selftests passed.\n');
end

function adjacencyCheck()
% Duplicating a one-edge slice makes the consequence of adjacency exact:
% connected extent is twice separate-slice extent for every resampling draw.
W=cell(8,1); values=[-2 -1 0 1 2 3 4 5]; group=[zeros(4,1);ones(4,1)];
for s=1:8, W{s}=repmat([0 values(s);values(s) 0],1,1,2); end
opts=struct('nPerm',9,'rngSeed',11,'t0',0.5,'tail','both');
checkDesign(group,opts);
model=struct('X',[ones(8,1) group],'C',[0 1],'statType','t');
for method={'freedman-lane','rowshuffle'}
    opts.method=method{1}; checkDesign(model,opts);
end
    function checkDesign(design,options)
        connected=mnbs_analyze(W,design,options);
        options.layerAdjacency='independent';
        separate=mnbs_analyze(W,design,options);
        assert(isequal(connected.stats.Tef,separate.stats.Tef));
        assert(~isempty(separate.clusters) && all([separate.clusters.extent]==2));
        assert(all(connected.nullMax==2*separate.nullMax));
        assert(all(arrayfun(@(c)numel(c.layerBins)==1,separate.clusters)));
    end
end

function assertThrows(callback)
failed=false;
try, callback(); catch, failed=true; end
assert(failed,'Expected invalid input to be rejected.');
end

function goldenCheck()
% Python has checked this fixed data against SciPy and an independent OLS
% formula. Executing this block in MATLAB is still required for parity.
fixture=jsondecode(fileread(fullfile(fileparts(mfilename('fullpath')),'golden_fixture.json')));
y=fixture.y; edges=[1 2;1 3;2 3]; W=cell(size(y,1),1);
for s=1:numel(W)
    M=zeros(3,3,2);
    for e=1:3
        for f=1:2
            M(edges(e,1),edges(e,2),f)=y(s,2*(e-1)+f);
            M(edges(e,2),edges(e,1),f)=y(s,2*(e-1)+f);
        end
    end
    W{s}=M;
end
stats=mnbs_edgestat_group(W,fixture.group,struct('tail','both'));
assert(max(abs(stats.Tef(:)-fixture.expected_welch(:)))<1e-10);
clusters=mnbs_components(stats.Tef,stats.iUT,stats.jUT,3,3,'both','mass');
assert(numel(clusters)==numel(fixture.clusters));
for k=1:numel(clusters)
    expected=fixture.clusters(k);
    [nodes,bins]=ind2sub([3 2],clusters(k).nodeFreqIdx);
    assert(isequal([nodes bins],expected.sites));
    assert(strcmp(clusters(k).tail,expected.tail) && clusters(k).extent==expected.extent);
    assert(abs(clusters(k).mass-expected.mass)<1e-10);
    assert(abs(clusters(k).intensity-expected.intensity)<1e-10);
end
model=struct('X',fixture.X,'C',fixture.C(:)','statType','t');
glm=mnbs_edgestat_glm(W,model,struct('tail','both'));
assert(max(abs(glm.Tef(:)-fixture.expected_glm_t(:)))<1e-10);
model.statType='F';
glm=mnbs_edgestat_glm(W,model,struct('tail','right'));
assert(max(abs(glm.Tef(:)-fixture.expected_glm_f(:)))<1e-10);
% A harmless change in units should not drop an estimable regressor.
model.X(:,2)=model.X(:,2)*1e-6; model.C(2)=model.C(2)*1e-6;
model.statType='t';
glm=mnbs_edgestat_glm(W,model,struct('tail','both'));
assert(max(abs(glm.Tef(:)-fixture.expected_glm_t(:)))<1e-8);
end
