function [W,group,frequencies,nodeLabels] = mnbs_demo(seed)
%MNBS_DEMO Generate a small synthetic dataset in MATLAB.
%
%   [W, group, frequencies, nodeLabels] = mnbs_demo()
%   [W, group, frequencies, nodeLabels] = mnbs_demo(seed)
%
%   Returns 40 simulated observations (two groups of 20) of a 12-region
%   network in 10 frequency bins (4-22 Hz). Group 1 has a positive effect
%   along regions 1-4 in bins 3-6. Use it to try the functions without data;
%   it is not a validation of statistical power. The bundled datasets shared
%   with Python and the app are loaded with MNBS_LOAD_DEMO.
%
%   Inputs
%     seed   random seed [7]
%
%   Outputs
%     W            S-by-1 cell of N-by-N-by-L matrices
%     group        S-by-1 numeric labels (1 or 2)
%     frequencies  1-by-L axis values (Hz)
%     nodeLabels   1-by-N cell of region names
%
%   Example
%     [W, group, f] = mnbs_demo();
%     result = mnbs_analyze(W, group, struct('nPerm', 499, 'axisName', 'Frequency', ...
%                                           'axisUnit', 'Hz', 'axisValues', f));
%
%   See also MNBS_LOAD_DEMO, MNBS_ANALYZE.
%
%   Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
%   https://github.com/Minarose/multiplex-nbs
if nargin<1, seed=7; end
old=rng; restore=onCleanup(@()rng(old)); %#ok<NASGU>
rng(seed,'twister');
S=40; N=12; F=10;
W=cell(S,1); group=[ones(S/2,1);2*ones(S/2,1)];
frequencies=4:2:22;
nodeLabels=arrayfun(@(n)sprintf('Node %02d',n),1:N,'UniformOutput',false);
for s=1:S
    M=zeros(N,N,F);
    for f=1:F
        A=triu(randn(N),1);
        if group(s)==1 && ismember(f,3:6)
            for n=1:3, A(n,n+1)=A(n,n+1)+1.6; end
        end
        M(:,:,f)=A+A';
    end
    W{s}=M;
end
end
