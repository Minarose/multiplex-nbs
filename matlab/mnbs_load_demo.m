function d = mnbs_load_demo(name)
%MNBS_LOAD_DEMO Load a bundled practice dataset (all observations simulated).
%
%   d = mnbs_load_demo()
%   d = mnbs_load_demo(name)
%
%   The same datasets as the Python package (multiplex_nbs.load_demo) and the
%   desktop app, so results agree across tools.
%
%   Inputs
%     name  'brain-network' (default): 32 regions of an open human structural
%                 connectome with MNI coordinates, 40 simulated participants in
%                 two groups, 8 time windows (0-350 ms); group 1 is higher
%                 along a left sensorimotor-parietal chain at 100-200 ms.
%           'two-sample', 'paired', 'glm': 12 abstract regions, 8 frequency
%                 bins (4-18 Hz), one study design each.
%
%   Output
%     d  struct with .W (S-by-1 cell of N-by-N-by-L), .axisName, .axisUnit,
%        .axisValues, .nodeLabels, .description, and the design: .group
%        (labels or pair IDs) or .model (.X, .C, .statType). The brain
%        example also has .nodeCoordinates (MNI mm) and .groupNames.
%
%   Example
%     d = mnbs_load_demo('glm');
%     result = mnbs_analyze(d.W, d.model, struct('nPerm', 499));
%
%   See also MNBS_ANALYZE, MNBS_DEMO.
%
%   Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
%   https://github.com/Minarose/multiplex-nbs

if nargin < 1, name = 'brain-network'; end
files = struct('brain_network', 'demo_brain_network.mat', 'two_sample', 'demo_two_sample.mat', ...
               'paired', 'demo_paired.mat', 'glm', 'demo_glm.mat');
key = strrep(lower(char(name)), '-', '_');
if ~isfield(files, key)
    error('mnbs_load_demo:name', 'Unknown demo "%s". Use brain-network, two-sample, paired or glm.', char(name));
end
folder = fullfile(fileparts(fileparts(mfilename('fullpath'))), 'data');
d = load(fullfile(folder, files.(key)));
d.W = d.W(:);
end
