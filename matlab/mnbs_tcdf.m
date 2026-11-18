function p = mnbs_tcdf(t, df)
%MNBS_TCDF Student-t cumulative distribution (base MATLAB only).
%
%   p = mnbs_tcdf(t, df)
%
%   Computed with the incomplete beta function, so the Statistics and
%   Machine Learning Toolbox is not needed. Used internally.
%
%   Multiplex-NBS 0.1.0 | Ismail MM, Williamson BJ, Kadis DS | GPL-3.0-or-later
%   https://github.com/Minarose/multiplex-nbs
z=betainc(df./(df+t.^2),df/2,0.5)/2;
p=z;
p(t>=0)=1-z(t>=0);
end
