import pylab as pl
from scipy import optimize
from pyQCD.interfaces import io
import pyQCD.interfaces.constants as const
import itertools
import sys

def pair_potential(b, r):
	"""Calculates the quark pair potential as b[0] * r - b[1] / r + b[2]"""
	return b[0] * r + b[1] / r + b[2]

def potential_params(data):
	"""Fits the curve(s) specified by data and returns the three parameters that
	characterise the potential"""
	if len(pl.shape(data)) == 1:
	
		r = pl.arange(1, pl.size(data) + 1)
		b0 = pl.array([1.0, 1.0, 1.0])

		err_func = lambda b, r, y: y - pair_potential(b, r)
		b, result = optimize.leastsq(err_func, b0, args = (r, data))

		if [1, 2, 3, 4].count(result) < 1:
			print("Warning! Fit failed.")

		return b

	else:
		b_store = pl.zeros((pl.size(data, axis = 0), 3))

		for i in xrange(pl.size(data, axis = 0)):
			b_store[i] = potential_params(data[i])

		return b_store

def calculate_potential(wilson_loops):
	"""Calculates the pair potential from the average wilson loops provided."""
	if len(pl.shape(wilson_loops)) == 2:
		potentials = pl.zeros(pl.size(wilson_loops, axis = 0))
		# The quark separations
		r = pl.arange(1, pl.size(wilson_loops, axis = 0) + 1)
		t = pl.arange(1, pl.size(wilson_loops, axis = 1) + 1)
		# The function we'll use to fit the Wilson loops
		f = lambda b, t, W: W - b[0] * pl.exp(-b[1] * t)
		
		for i in xrange(pl.size(wilson_loops, axis = 0)):
			params, result = optimize.leastsq(f, [1., 1.],
											  args = (t, wilson_loops[i]))
			potentials[i] = params[1]

	else:
		potentials = pl.zeros(pl.shape(wilson_loops)[:-1])

		for i in xrange(pl.size(wilson_loops, axis = 0)):
			potentials[i] = calculate_potential(wilson_loops[i])

	return potentials

def auto_correlation(plaquettes):
	"""Calculates the auto correlation function from a series of average
	plaquette values."""
	mean_plaquette = pl.mean(plaquettes)

	num_configs = pl.size(plaquettes, axis = 0) / 2

	auto_corr = pl.zeros(num_configs)

	for t in xrange(num_configs):
		auto_corr[t] = pl.mean((plaquettes - mean_plaquette) \
							   * (pl.roll(plaquettes, -t) - mean_plaquette))
	
	return auto_corr

def calculate_spacing(wilson_loops):
	"""Calculates the lattice spacing from a set of average wilson loops and
	the Sommer scale."""
	potentials = calculate_potential(wilson_loops)
	fit_params = potential_params(potentials)
	if len(pl.shape(fit_params)) > 1:
		return 0.5 / pl.sqrt((1.65 + fit_params[:,1]) / fit_params[:,0])
	else:
		return 0.5 / pl.sqrt((1.65 + fit_params[1]) / fit_params[0])

def compute_correlator(prop1, prop2, Gamma):
	"""Calculates correlator defined by interpolator Gamma"""

	# Do sums and traces over spin and colour
	# i, j, k, l, m and o represent spin indices
	# a and b are colour indices
	# Transpose of 1st propagator is done implicitly using
	# indices
	"""
	correlator = pl.einsum('ij,xjlab,lm,ximab->x',
						   Gamma2, pl.conj(prop1),
						   Gamma3, prop2).real
						   """

	# The above isn't very efficient. It's faster to split
	# it up into sepearate stages.

	Gamma2 = pl.dot(Gamma, const.gamma5)
	Gamma3 = pl.dot(const.gamma5, Gamma)
	
	# We now do the following Einstein sum, but using tensor dots
	# Note the requirement to swap axes back after the dot
	#product1 = pl.einsum('ij,xjlab->xilab',Gamma2,pl.conj(prop1))
	#product2 = pl.einsum('ij,xkjab->xkiab',Gamma3,prop2)
	
	product1 \
	  = pl.swapaxes(pl.tensordot(Gamma2, pl.conj(prop1), (1,1)),
					0, 1)
	product2 \
	  = pl.swapaxes(pl.tensordot(Gamma3, prop2, (1,2)),
					0,1)

	product2 = pl.swapaxes(product2,1,2)
	
	correlator = pl.einsum('xijab,xijab->x',product1,product2)
	
	return correlator.real

def meson_spec(prop_file1, prop_file2, lattice_shape, momentum):
	"""Calculates the 16 meson correlators"""

	num_props = len(prop_file1.keys())
	
	correlators = pl.zeros((num_props, lattice_shape[0], 17))
	Gammas = [G for Gs in const.Gammas.itervalues() for G in Gs]

	sites = list(itertools.product(xrange(lattice_shape[1]),
								   xrange(lattice_shape[2]),
								   xrange(lattice_shape[3])))

	momentum_prefactors = [2 * pl.pi / N for N in lattice_shape[1:]]
	
	for i, key in enumerate(prop_file1.keys()):

		print("Calculating correlators for propagator pair %d... " % i),
		sys.stdout.flush()

		prop1 = io.load_propagator(prop_file1, key)
		prop2 = io.load_propagator(prop_file2, key)

		correlators[i, :, 0] = pl.arange(lattice_shape[0])

		# Iterate through the 16 Gamma matrices in the consts file
		for j,Gamma in enumerate(Gammas):
			# Get the position space correlator
			pos_correl \
			  = pl.reshape(compute_correlator(prop1, prop2, Gamma),
						   (lattice_shape[0], len(sites)))
			# Get the exponential weighting factors for the momentum
			# projection
			exponentials \
			  = pl.exp(1j * pl.einsum('ij,j,j',
									  sites,
									  momentum,
									  momentum_prefactors))
			# Project onto the given momentum and store the result
			correlators[i, :, j + 1] \
			  = pl.einsum('ij,j', pos_correl, exponentials).real

		print("Done!")
		sys.stdout.flush()

	return correlators
