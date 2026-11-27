function fig = mnbs_gui()
%MNBS_GUI Open the MATLAB interface for Multiplex-NBS.
%
%   fig = mnbs_gui()
%
%   A local window to load a MAT file (W with group, or W with model), set
%   the analysis options, run the permutations with progress and
%   cancellation, view components and save the results. Requires MATLAB
%   R2021a or newer; no other toolbox and no internet connection is needed.
%   The standalone desktop app (no MATLAB needed) is available from the
%   project's Releases page.
%
%   See also MNBS_ANALYZE, MNBS_LOAD_DEMO.
%
%   Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
%   https://github.com/Minarose/multiplex-nbs
background=[0 0 0]; surface=[0.11 0.11 0.11]; ink=[0.96 0.96 0.96]; accent=[0.76 0.64 0.40];
fig=uifigure('Name','Multiplex-NBS | Node-layer inference', ...
    'Position',[80 80 1200 810],'Color',background);
outer=uigridlayout(fig,[3 2],'RowHeight',{64,'1x',30}, ...
    'ColumnWidth',{320,'1x'},'Padding',[20 14 20 10],'ColumnSpacing',18);
outer.BackgroundColor=background;
head=uilabel(outer,'Text','Multiplex-NBS','FontSize',27,'FontWeight','bold','FontColor',ink);
head.Layout.Column=[1 2];
sidebar=uipanel(outer,'Title','Set up an analysis','BackgroundColor',surface,'FontSize',15);
sidebar.Layout.Row=2; sidebar.Layout.Column=1;
form=uigridlayout(sidebar,[24 2],'ColumnWidth',{'1x','1x'}, ...
    'RowHeight',{30,34,46,23,30,23,30,23,30,23,30,23,30,23,30,26,23,30,28,34,34,40,'1x',30},'Padding',[14 12 14 12],'RowSpacing',4,'Scrollable','on');
form.BackgroundColor=surface;
section=uilabel(form,'Text','1  Choose your data','FontWeight','bold','FontColor',accent); section.Layout.Column=[1 2];
loadButton=uibutton(form,'Text','Open MAT file','ButtonPushedFcn',@loadData); loadButton.Layout.Row=2; loadButton.Layout.Column=1;
demoButton=uibutton(form,'Text','Try synthetic demo','ButtonPushedFcn',@loadDemo); demoButton.Layout.Row=2; demoButton.Layout.Column=2;
info=uilabel(form,'Text','Start with the demo or load a dataset.','WordWrap','on','FontColor',ink); info.Layout.Row=3; info.Layout.Column=[1 2];
label(form,'Third axis name                 Unit (optional)',4);
axisName=uieditfield(form,'text','Value','Layer','ValueChangedFcn',@invalidate); axisName.Layout.Row=5; axisName.Layout.Column=1;
axisUnit=uieditfield(form,'text','Value','','ValueChangedFcn',@invalidate); axisUnit.Layout.Row=5; axisUnit.Layout.Column=2;
label(form,'Connections between slices',6);
adjacency=uidropdown(form,'Items',{'consecutive','independent'},'ValueChangedFcn',@invalidate); adjacency.Layout.Row=7; adjacency.Layout.Column=[1 2];
label(form,'Design',8);
test=uidropdown(form,'Items',{'Independent groups','Paired observations','GLM contrast'},'ValueChangedFcn',@invalidate); test.Layout.Row=9; test.Layout.Column=[1 2];
label(form,'Primary statistic threshold',10);
threshold=uieditfield(form,'numeric','Value',3,'Limits',[0 Inf],'LowerLimitInclusive','off','ValueChangedFcn',@invalidate); threshold.Layout.Row=11; threshold.Layout.Column=[1 2];
label(form,'Direction / tail',12);
tail=uidropdown(form,'Items',{'Right (positive)','Left (negative)','Both (joint correction)'},'ValueChangedFcn',@invalidate); tail.Layout.Row=13; tail.Layout.Column=[1 2];
label(form,'Cluster statistic',14);
metric=uidropdown(form,'Items',{'Extent: node-layer sites','Mass: summed edge statistics'},'ValueChangedFcn',@invalidate); metric.Layout.Row=15; metric.Layout.Column=[1 2];
% Intensity is mass with the threshold subtracted from each edge, offered only under Mass.
subtract=uicheckbox(form,'Text','Subtract the threshold from each edge (= NBS intensity)','Value',false,'Enable','off', ...
    'Tooltip',['Sums each edge statistic minus the threshold instead of the full statistic. This equals ' ...
    'intensity in the NBS toolbox, and results are labelled intensity.'],'ValueChangedFcn',@invalidate);
subtract.Layout.Row=16; subtract.Layout.Column=[1 2];
label(form,'Permutations                     Random seed',17);
perms=uieditfield(form,'numeric','Value',9999,'Limits',[1 Inf],'RoundFractionalValues','on','ValueChangedFcn',@invalidate); perms.Layout.Row=18; perms.Layout.Column=1;
seed=uieditfield(form,'numeric','Value',1,'Limits',[0 2^32-1],'RoundFractionalValues','on','ValueChangedFcn',@invalidate); seed.Layout.Row=18; seed.Layout.Column=2;
absolute=uicheckbox(form,'Text','Use absolute connectivity','Value',false,'ValueChangedFcn',@invalidate); absolute.Layout.Row=19; absolute.Layout.Column=[1 2];
runButton=uibutton(form,'Text','Run analysis','FontWeight','bold','BackgroundColor',accent,'FontColor',background,'ButtonPushedFcn',@runAnalysis,'Enable','off'); runButton.Layout.Row=20; runButton.Layout.Column=[1 2];
exportButton=uibutton(form,'Text','Save results and summary','ButtonPushedFcn',@exportResults,'Enable','off'); exportButton.Layout.Row=21; exportButton.Layout.Column=[1 2];
notes=uilabel(form,'Text','Group direction: lower label minus higher label. Paired: first row minus second row within each ID.','WordWrap','on','FontSize',11); notes.Layout.Row=22; notes.Layout.Column=[1 2];
helpButton=uibutton(form,'Text','Input guide','ButtonPushedFcn',@showHelp); helpButton.Layout.Row=24; helpButton.Layout.Column=1;
classicButton=uibutton(form,'Text','Original NBS','ButtonPushedFcn',@openOriginalNBS); classicButton.Layout.Row=24; classicButton.Layout.Column=2;
content=uigridlayout(outer,[4 1],'RowHeight',{50,'1.3x','1x','0.8x'},'Padding',[0 0 0 0]); content.Layout.Row=2; content.Layout.Column=2;
content.BackgroundColor=background;
status=uilabel(content,'Text','Explore connected effects across nodes and time, frequency, or another axis.','WordWrap','on','FontSize',16,'FontColor',ink);
heat=uiaxes(content); heat.Layout.Row=2; title(heat,'Node × layer cluster membership'); xlabel(heat,'Layer'); ylabel(heat,'Node');
histogramAxes=uiaxes(content); histogramAxes.Layout.Row=3; title(histogramAxes,'Permutation maximum distribution'); xlabel(histogramAxes,'Maximum cluster statistic'); ylabel(histogramAxes,'Count');
clusterTable=uitable(content,'Data',table(),'RowName',{}); clusterTable.Layout.Row=4;
foot=uilabel(outer,'Text','Local analysis • Cluster-level inference • Explicit layer adjacency • Version 0.3.0','FontColor',[0.62 0.70 0.78],'FontSize',11); foot.Layout.Row=3; foot.Layout.Column=[1 2];
W=[]; group=[]; model=[]; blocks=[]; result=[]; frequencies=[]; nodeLabels={}; datasetName=''; busy=false;
for ax=[heat histogramAxes]
    ax.Color=surface; ax.XColor=ink; ax.YColor=ink; ax.GridColor=[0.3 0.37 0.45];
    ax.Title.Color=ink; ax.XLabel.Color=ink; ax.YLabel.Color=ink;
end
clusterTable.BackgroundColor=surface; clusterTable.FontColor=ink;
for control=reshape(findall(fig,'-property','FontColor'),1,[])
    if ~isequal(control,runButton), control.FontColor=ink; end
end
for control=reshape(findall(form,'-property','BackgroundColor'),1,[])
    if ~isequal(control,runButton), control.BackgroundColor=surface; end
end
for control=reshape(findall(fig,'-property','FontName'),1,[])
    control.FontName='Arial';
end
controls={axisName,axisUnit,adjacency,loadButton,demoButton,test,threshold,tail,metric,subtract,perms,seed,absolute,runButton};

    function openOriginalNBS(~,~)
        if exist('NBS','file') ~= 2
            uialert(fig,['Install NBS Connectome from nitrc.org/projects/nbs/ and add ' ...
                'the toolbox to your MATLAB path to open its original interface.'],'Original NBS');
            return
        end
        NBS;
    end

    function loadDemo(~,~)
        [W,group,frequencies,nodeLabels]=mnbs_demo(); model=[]; blocks=[];
        axisName.Value='Frequency'; axisUnit.Value='Hz'; adjacency.Value='consecutive';
        datasetName='Synthetic demonstration'; test.Value='Independent groups';
        tail.Value='Right (positive)'; threshold.Value=3; perms.Value=9999;
        dataReady();
    end
    function loadData(~,~)
        [name,path]=uigetfile('*.mat','Choose a connectivity dataset');
        if isequal(name,0), return; end
        try
            data=load(fullfile(path,name));
            if isfield(data,'W')
                newW=data.W;
                if isnumeric(newW)
                    if ndims(newW)>4 || size(newW,1)~=size(newW,2)
                        error('Numeric MAT variable W must be N-by-N-by-F-by-S.');
                    end
                    matrices=newW; newW=cell(size(matrices,4),1);
                    for s=1:numel(newW), newW{s}=matrices(:,:,:,s); end
                end
            elseif isfield(data,'connectivity')
                newW=data.connectivity; % Explicit Python S-by-N-by-N-by-F order.
            else
                error('The MAT file must contain W (cells or N-by-N-by-F-by-S), or connectivity (S-by-N-by-N-by-F).');
            end
            newGroup=[]; newModel=[]; newBlocks=[]; newFreq=[]; newLabels={}; newAxis='Layer'; newUnit=''; newAdj='consecutive';
            if isfield(data,'group'), newGroup=data.group; end
            if isfield(data,'model'), newModel=data.model;
            elseif isfield(data,'X') && isfield(data,'C')
                type='t'; if isfield(data,'stat_type'), type=char(data.stat_type); end
                newModel=struct('X',data.X,'C',data.C,'statType',type);
            end
            if isempty(newGroup) && isempty(newModel), error('Include group labels or a model with X, C and statType.'); end
            if isfield(data,'exchange_blocks'), newBlocks=data.exchange_blocks; end
            if isfield(data,'exchangeBlocks'), newBlocks=data.exchangeBlocks; end
            if isfield(data,'frequencies'), newFreq=data.frequencies; newAxis='Frequency'; end
            if isfield(data,'axis_values'), newFreq=data.axis_values; end
            if isfield(data,'axis_name'), newAxis=char(data.axis_name); end
            if isfield(data,'axis_unit'), newUnit=char(data.axis_unit); end
            if isfield(data,'layer_adjacency'), newAdj=validatestring(char(data.layer_adjacency),{'consecutive','independent'}); end
            if isfield(data,'node_labels'), newLabels=cellstr(string(data.node_labels)); end
            if isfield(data,'nodeLabels'), newLabels=cellstr(string(data.nodeLabels)); end
            W=newW; nodeLabels=newLabels; group=newGroup; model=newModel; blocks=newBlocks; frequencies=newFreq;
            axisName.Value=newAxis; axisUnit.Value=newUnit; adjacency.Value=newAdj;
            datasetName=name;
            if ~isempty(model), test.Value='GLM contrast'; else, test.Value='Independent groups'; end
            dataReady();
        catch err
            uialert(fig,err.message,'Could not load dataset');
        end
    end
    function dataReady()
        invalidate(); runButton.Enable='on';
        if iscell(W), S=numel(W); N=size(W{1},1); F=size(W{1},3);
        else, S=size(W,1); N=size(W,2); F=size(W,4); end
        info.Text=sprintf('%s\n%d observations · %d nodes · %d layers',datasetName,S,N,F);
        status.Text='Data loaded. Choose your analysis settings, then run.';
    end
    function syncSubtract()
        if startsWith(metric.Value,'Mass') && ~busy, subtract.Enable='on'; else, subtract.Enable='off'; end
    end
    function invalidate(varargin)
        if busy, return; end
        syncSubtract();
        switch test.Value
            case 'Independent groups', notes.Text='Positive direction: lower numeric group label minus higher label.';
            case 'Paired observations', notes.Text='Positive direction: first row minus second row within each pair ID.';
            case 'GLM contrast', notes.Text='Direction: model contrast Cβ. GLM uses Freedman–Lane. F requires the right tail.';
        end
        result=[]; exportButton.Enable='off'; clusterTable.Data=table();
        cla(heat); cla(histogramAxes); status.Text='Settings changed. Run the analysis to see current results.';
    end
    function runAnalysis(~,~)
        if isempty(W), return; end
        invalidate(); busy=true; setControls('off');
        progress=uiprogressdlg(fig,'Title','Running extended NBS','Message','Computing observed statistics…','Value',0,'Cancelable','on');
        cleanup=onCleanup(@finishRun); %#ok<NASGU>
        try
            tails={'right','left','both'}; tailIndex=find(strcmp(tail.Value,tail.Items));
            metricName='extent';
            if startsWith(metric.Value,'Mass'), metricName='mass'; if subtract.Value, metricName='intensity'; end; end
            options=struct('t0',threshold.Value,'tail',tails{tailIndex}, ...
                'clusterMetric',metricName,'nPerm',perms.Value,'rngSeed',seed.Value, ...
                'useAbs',absolute.Value,'exchangeBlocks',blocks,'progress',@updateProgress, ...
                'axisName',axisName.Value,'axisUnit',axisUnit.Value,'axisValues',frequencies, ...
                'layerAdjacency',adjacency.Value);
            design=group;
            switch test.Value
                case 'Paired observations', options.test='paired';
                case 'GLM contrast'
                    if isempty(model), error('Load a MAT file with model.X, model.C and model.statType to run a GLM.'); end
                    design=model;
                otherwise
                    if isempty(group), error('This dataset has no group labels. Choose GLM contrast.'); end
            end
            drawnow;
            result=mnbs_analyze(W,design,options);
            renderResult(); exportButton.Enable='on';
        catch err
            result=[]; exportButton.Enable='off';
            status.Text='Analysis stopped. No results were saved.';
            if ~strcmp(err.identifier,'mnbs_analyze:Cancelled'), uialert(fig,err.message,'Analysis could not finish'); end
        end
        function updateProgress(p,total)
            if ~isvalid(fig) || progress.CancelRequested
                error('mnbs_analyze:Cancelled','Analysis cancelled.');
            end
            if mod(p,max(1,floor(total/100)))==0 || p==total
                progress.Value=p/total; progress.Message=sprintf('Permutation %d of %d',p,total); drawnow;
            end
        end
        function finishRun()
            if isvalid(progress), close(progress); end
            busy=false;
            if isvalid(fig), setControls('on'); syncSubtract(); end
        end
    end
    function setControls(value)
        for k=1:numel(controls), controls{k}.Enable=value; end
    end
    function renderResult()
        C=result.clusters; N=result.stats.nNodes; F=result.stats.nFreq;
        membership=zeros(N,F);
        for k=1:numel(C)
            if C(k).p_FWE<=0.05, membership(C(k).nodeFreqIdx)=membership(C(k).nodeFreqIdx)+1; end
        end
        imagesc(heat,1:F,1:N,membership); heat.YDir='normal'; colormap(heat,[0.11 0.11 0.11; lines(max(1,max(membership(:))))]);
        caxis(heat,[0 max(1,max(membership(:)))]);
        bar=colorbar(heat); bar.Label.String='Number of significant clusters'; bar.Color=ink; bar.Label.Color=ink;
        axisLabel=result.axis.name;
        if ~isempty(result.axis.unit), axisLabel=[axisLabel ' (' result.axis.unit ')']; end
        xlabel(heat,axisLabel); ylabel(heat,'Node');
        heat.XTick=1:F; heat.XTickLabel=compose('%.3g',result.axis.values(:));
        if numel(nodeLabels)==N && N<=30
            heat.YTick=1:N; heat.YTickLabel=nodeLabels;
        end
        title(heat,'Significant cluster coverage (descriptive sites, p_{FWE} ≤ 0.05)');
        histogram(histogramAxes,result.nullMax,'FaceColor',accent,'EdgeColor','none');
        xlabel(histogramAxes,['Maximum cluster ' result.options.clusterMetric]); ylabel(histogramAxes,'Permutations');
        title(histogramAxes,'Null maximum distribution');
        if ~isempty(C)
            xline(histogramAxes,max([C.testStat]),'--','Largest observed','Color',[0.75 0.28 0.16],'LineWidth',1.5);
            weightName='Mass'; weights=[C.mass]';
            if strcmp(result.options.clusterMetric,'intensity'), weightName='Intensity'; weights=[C.intensity]'; end
            clusterTable.Data=table([C.id]',string({C.tail})',[C.extent]',weights,[C.p_FWE]', ...
                'VariableNames',{'Cluster','Tail','Extent',weightName,'p_FWE'});
        else
            clusterTable.Data=table();
        end
        status.Text=sprintf('%d cluster(s) found · %d at pFWE ≤ 0.05\n%d permutations · %s · minimum p = %.5g', ...
            numel(C),result.report.nSig,numel(result.nullMax),result.method,1/(numel(result.nullMax)+1));
    end
    function exportResults(~,~)
        if isempty(result), return; end
        [name,path]=uiputfile('*.mat','Save analysis results','multiplex_nbs_results.mat');
        if isequal(name,0), return; end
        try
            save(fullfile(path,name),'result','datasetName','frequencies','nodeLabels');
            [~,stem]=fileparts(name);
            writetable(clusterTable.Data,fullfile(path,[stem '_clusters.csv']));
            status.Text=['Saved results: ' name];
        catch err, uialert(fig,err.message,'Could not save results'); end
    end
    function showHelp(~,~)
        message=sprintf(['W: cell array of N × N × F symmetric, finite connectivity matrices, one per observation. In MAT files, numeric W uses N × N × F × S; connectivity uses S × N × N × F.\n\n' ...
            'group: numeric labels (two groups), or pair IDs (each occurs twice). GLM: model.X, model.C, model.statType (t/F). Optional exchangeBlocks restrict permutations within blocks.\n\n' ...
            'F statistics require the right tail. Choose consecutive slices only when adjacency is meaningful. Independent slices are corrected together. Both tails are corrected together. GLMs use Freedman–Lane; advanced methods are available in the command-line API.\n\n' ...
            'A significant cluster does not establish individual node, edge or layer significance. Permutation validity depends on exchangeability. The synthetic demo demonstrates operation, not sensitivity or specificity.']);
        uialert(fig,message,'Using extended NBS','Icon','info');
    end
end

function label(parent,text,row)
control=uilabel(parent,'Text',text,'FontSize',11,'FontColor',[0.36 0.42 0.45]);
control.Layout.Row=row; control.Layout.Column=[1 2];
end
