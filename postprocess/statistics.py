import pylab as pl

def bin(X, binsize = 1):
	"""Split X into bins and return the average of each bin"""
	if binsize == 1:
		return X;
	else:
		extra = 0 if pl.size(X, axis = 0) % binsize == 0 else 1
		dims = [i for i in pl.shape(Ws)]
		dims[0] = dims[0] / binsize + extra
		dims = tuple(dims)
		X_binned = pl.zeros(dims)

		for i in xrange(pl.size(X_binned, axis = 0)):
			X_binned[i] = pl.mean(X[i * binsize:(i + 1) * binsize], axis = 0)

		return X_binned

def bootstrap(X):
	"""Performs a bootstrap resampling of X"""
	return X[pl.randint(0, pl.size(X, axis = 0), pl.size(X, axis = 0))]