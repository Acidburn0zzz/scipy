"""
A basic linear programming function using a simplex method.

Functions
---------
.. autosummary::
   :toctree: generated/

    linprog
    lpsimplex
    verbose_callback
    terse_callback

"""

from __future__ import division, print_function, absolute_import

import numpy as np
import numpy.ma as ma

from .optimize import Result, _check_unknown_options

__all__ = ['linprog','lpsimplex','liprog_verbose_callback','linprog_terse_callback']

__docformat__ = "restructuredtext en"


def linprog_verbose_callback(xk,**kwargs):
    """
    This is a sample callback for use with linprog, demonstrating the callback interface.
    This callback produces detailed output to sys.stdout before each iteration and after
    the final iteration of the simplex algorithm.

    Parameters
    ----------
    xk : array_like
        The current solution vector.
    **kwargs : dict
        A dictionary containing the following parameters:

        tableau : array_like
            The current tableau of the simplex algorithm.  Its structure is defined in lpsimplex.
        vars : tuple(str,...)
            Column headers for each column in tableau. "x[i]" for actual variables,
            "s[i]" for slack surplus variables, "a[i]" for artificial variables,
            and "RHS" for the constraint RHS vector
        phase : int
            The current Phase of the simplex algorithm (1 or 2)
        iter : int
            The current iteration number.
        pivot : tuple(int,int)
            The index of the tableau selected as the next pivot, or nan if no pivot exists
        basics : list[tuple(int,float)]
            A list of the current basic variables.  Each element contains the name of a basic variable and
            its value.
        complete : bool
            True if the simplex algorithm has completed (and this is the final call to callback), otherwise False.
    """
    tableau = kwargs["tableau"]
    columns = kwargs["vars"]
    iter = kwargs["iter"]
    pivrow,pivcol = kwargs["pivot"]
    phase = kwargs["phase"]
    basics = kwargs["basics"]
    complete = kwargs["complete"]

    t_rows,t_cols = tableau.shape

    saved_printoptions = np.get_printoptions()
    np.set_printoptions(linewidth=256,
                        formatter={'float':lambda x: "{: 12.4f}".format(x)})
    if complete:
        print("--------- Iteration Complete - Phase {:d} -------\n".format(phase))
        print("Tableau:")
    elif iter == 0:
        print("--------- Initial Tableau - Phase {:d} ----------\n".format(phase))

    else:
        print("--------- Iteration {:d}  - Phase {:d} --------\n".format(iter,phase))
        print("Tableau:")

    if iter >= 0:
        print(" " + "".join(["{:>13}".format(columns[i]) for i in range(t_cols)]))
        print("" + str(tableau) + "\n")
        if not complete:
            print("Pivot Element: T[{:.0f},{:.0f}]\n".format(pivrow,pivcol))
        print("Basic Variables:"),
        for basic_var in basics:
            print("{:<5s} = {: f}".format(columns[basic_var[0]],basic_var[1]))
        print()
        print("Current Solution:")
        print("x = ", xk)
        print()
        print("Current Objective Value:")
        print("f = ", tableau[-1,-1])
        print()
    np.set_printoptions(**saved_printoptions)


def linprog_terse_callback(xk, **kwargs):
    """
    This is a sample callback for use with linprog, demonstrating the callback interface.
    This callback produces brief output to sys.stdout before each iteration and after
    the final iteration of the simplex algorithm.

    Parameters
    ----------
    xk : array_like
        The current solution vector.
    **kwargs : dict
        A dictionary containing the following parameters:

        tableau : array_like
            The current tableau of the simplex algorithm.  Its structure is defined in lpsimplex.
        vars : tuple(str,...)
            Column headers for each column in tableau. "x[i]" for actual variables,
            "s[i]" for slack surplus variables, "a[i]" for artificial variables,
            and "RHS" for the constraint RHS vector
        phase : int
            The current Phase of the simplex algorithm (1 or 2)
        nit : int
            The current iteration number.
        pivot : tuple(int,int)
            The index of the tableau selected as the next pivot, or nan if no pivot exists
        basics : list[tuple(int,float)]
            A list of the current basic variables.  Each element contains the index of a basic variable and
            its value.
        complete : bool
            True if the simplex algorithm has completed (and this is the final call to callback), otherwise False.
    """
    iter = kwargs["iter"]

    if iter == 0:
        print("Iter:   X:")
    print("{: <5d}   ".format(iter),end="")
    print(xk)


def _get_basics(tableau):
    """
    Given a tableau, return the indices of the basic columns and the corresponding
    values of the basic variables.

    Parameters
    ----------
    tableau : array_like
        A 2-D array representing the current for of the tableau for the simplex method in standard form.

    Returns
    -------
    indices : array_like
        An array of ints where each value is the index of a basic column in the tableau.
    values : array_like
        An array of floats where each value is the value of a basic variable whose column
        is given by the corresponding index in indices.
    """
    indices = []
    values = []
    count = 0
    n,m = tableau.shape
    for col in range(m-1):
        ones_in_col = tableau[:,col] == 1.0
        zeros_in_col = tableau[:,col] == 0.0
        if ones_in_col.sum() == 1 and zeros_in_col.sum() == n-1:
            # Column is basic
            nonzero_row = np.nonzero(tableau[:-1,col])[0][0]
            indices.append(col)
            values.append(tableau[nonzero_row,-1])
    return np.asarray(indices,dtype=np.int),np.asarray(values,dtype=np.float64)


def lpsimplex(tableau,n,n_slack,n_artificial,maxiter=1000,phase=2,callback=None,tol=1.0E-12,nit0=0):
    """
    Solve a linear programming problem in "standard maximization form" using the Simplex Method.

    Maximize :math:`f = c^T x`

    subject to

    .. math::

        Ax = b
        x_i >= 0
        b_j >= 0

    Parameters
    ----------
    tableau : array_like
        A 2-D array representing the simplex tableau corresponding to the maximization problem.
        It should have the form:

        [[A[0,0], A[0,1], ..., A[0,n_total], b[0]],
         [A[1,0], A[1,1], ..., A[1,n_total], b[1]],
         .
         .
         .
         [A[m,0], A[m,1], ..., A[m,n_total], b[m]],
         [c[0],   c[1], ...,   c[n_total],    0]]

        for a Phase 2 problem, or the form:

        [[A[0,0], A[0,1], ..., A[0,n_total], b[0]],
         [A[1,0], A[1,1], ..., A[1,n_total], b[1]],
         .
         .
         .
         [A[m,0], A[m,1], ..., A[m,n_total], b[m]],
         [c[0],   c[1], ...,   c[n_total],   0],
         [c'[0],  c'[1], ...,  c'[n_total],  0]]

         for a Phase 1 problem (a Problem in which a basic feasible solution is sought
         prior to maximizing the actual objective. n_total is the total of all variables:

    n : int
        The number of true variables in the problem.
    n_slack : int
        The number of slack/surplus variables in the problem.
    n_artificial : int
        The number of artificial variables in the problem.
    maxiter : int
        The maximum number of iterations to perform before aborting the optimization.
    phase : int
        The phase of the optimization being executed.  In phase 1 a basic feasible solution is sought and
        the tableau has an additional row representing an alternate objective function.
    callback : callable
        If a callback function is provided, it will be called within each iteration of the simplex algorithm.
        The callback must have the signature `callback(xk,**kwargs)` where xk is the current solution vector
        and kwargs is a dictionary containing the following::
        "tableau" : The current Simplex algorithm tableau
        "nit" : The current iteration.
        "pivot" : The pivot (row,column) used for the next iteration.
        "phase" : Whether the algorithm is in Phase 1 or Phase 2.
        "bv" : A structured array containing a string representation of each basic variable and its current value.
    tol : float
        The tolerance which determines when a solution is "close enough" to zero in Phase 1 to be considered
        a basic feasible solution or close enough to positive to to serve as an optimal solution.
    nit0 : int
        The initial iteration number used to keep an accurate iteration total in a two-phase problem.

    Returns
    -------
    res : Result
        The optimization result represented as a ``Result`` object.
        Important attributes are: ``x`` the solution array, ``success`` a
        Boolean flag indicating if the optimizer exited successfully and
        ``message`` which describes the cause of the termination. Possible
        values for the ``status`` attribute are:
        -1 : Invalid arguments
         0 : Optimization terminated successfully
         1 : Iteration limit reached
         2 : Problem appears to be infeasible
         3 : Problem appears to be unbounded

        See `Result` for a description of other attributes.
    """

    nit = nit0

    if phase not in (1,2):
        status = -1
        message = "Invalid input to lpsimplex.  Phase must be 1 or 2."

    # Make a copy of the tableau that will be used to detect cycling
    tableau0 = np.empty_like(tableau)
    tableau0[:,:] = tableau

    t_rows, t_cols = tableau.shape

    pivrow = 0
    pivcol = 0

    status = None
    message = ""
    cycle = 0
    x = np.zeros(n)

    if not callback is None:
        index_to_varname = {}
        for i in range(n):
            index_to_varname[i] = 'x[{:d}]'.format(i)
        for i in range(n_slack):
            index_to_varname[n+i] = 's[{:d}]'.format(i)
        for i in range(n_artificial):
            index_to_varname[n+n_slack+i] = 'a[{:d}]'.format(i)
        column_headers = [index_to_varname[i] for i in range(t_cols - 1)] + ["RHS"]

    while nit < maxiter and status is None:

        if nit > 2**n:
            if np.all(tableau == tableau0):
                cycle += 1

        # Find the most negative value in bottom row of tableau
        pivcol = np.argmin(tableau[-1,:-1])

        # sort the pivot column so that later we don't bother with rows where
        # the value in pivot column is negative
        if phase == 1:
            pivcol_sortorder = np.argsort(tableau[:-2, pivcol])[:,np.newaxis]
        else:
            pivcol_sortorder = np.argsort(tableau[:-1, pivcol])[:,np.newaxis]

        # Now row quotient has three columns: the original row index,
        # the value in the pivot column, and the RHS value
        row_quotient = np.hstack([pivcol_sortorder,
                                  tableau[pivcol_sortorder, pivcol],
                                  tableau[pivcol_sortorder, -1]])
        # Pare down row_quotient by removing those rows where the value in the
        # pivot column is non-positive
        row_quotient = row_quotient[row_quotient[:,1] > 0]

        # Replace the 2nd column the ratio of the RHS value / pivot column value
        row_quotient[:,1] = row_quotient[:,2] / row_quotient[:,1]

        # Sort row quotient
        # With the negative column values removed, we now want to use the row with the minimum
        # quotient (in column 1) as the pivot row.
        try:
            row_quotient = row_quotient[row_quotient[:,1].argsort(),:1]
            pivrow = row_quotient[cycle][0]
        except IndexError:
            pivrow = np.nan
            if cycle > 0:
                message = "Optimization failed. The problem appears to " \
                          "be unbounded. Unable to recover from cycling."
            status = 3
            message = "Optimization failed. The problem appears to be unbounded."
            break

        if cycle > 0:
            cycle = 0

        if np.all(tableau[-1,:-1] >= -tol):
            status = 0

        if not callback is None:
            basic_i,basic_val = _get_basics(tableau)
            basic_vars = zip(basic_i.tolist(),basic_val.tolist())
            x.fill(0.0)
            for i in range(len(basic_vars)):
                if basic_i[i] < n:
                    x[basic_i[i]] = basic_val[i]
                else:
                    break

            callback(x, **{"tableau": tableau,
                            "iter":nit,
                            "vars":column_headers,
                            "pivot":(pivrow,pivcol),
                            "phase":phase,
                            "basics":basic_vars,
                            "complete": (not status is None) and phase == 2})

        if status is None:
            pivval = tableau[pivrow,pivcol]
            tableau[pivrow,:] = tableau[pivrow,:] / pivval
            for irow in range(tableau.shape[0]):
                if irow != pivrow:
                    tableau[irow,:] = tableau[irow,:] \
                                      - tableau[pivrow,:]*tableau[irow,pivcol]

            nit += 1

    else:
        if nit >= maxiter:
            message = "Iteration limit reached."
            status = 1
        else:
            message = "Optimization terminated successfully."
            status = 0

    basic_i,basic_val = _get_basics(tableau)
    x.fill(0.0)
    for i in range(len(basic_i)):
        if basic_i[i] < n:
            x[basic_i[i]] = basic_val[i]
        else:
            break

    return x, nit, status, message


def _simplex(H,basis,indx,s,maxiter=1000):
    """
    Solve a linear programming problem in "standard maximization form" using the Simplex Method.

    Maximize :math:`f = c^T x`

    subject to

    .. math::

        Ax = b
        x_i >= 0
        b_j >= 0

    Parameters
    ----------
    H : array_like
        A 2-D array representing the simplex tableau corresponding to the maximization problem.
        It should have the form:

        [[A[0,0], A[0,1], ..., A[0,n_total], b[0]],
         [A[1,0], A[1,1], ..., A[1,n_total], b[1]],
         .
         .
         .
         [A[m,0], A[m,1], ..., A[m,n_total], b[m]],
         [c[0],   c[1], ...,   c[n_total],    0]]

        for a Phase 2 problem, or the form:

        [[A[0,0], A[0,1], ..., A[0,n_total], b[0]],
         [A[1,0], A[1,1], ..., A[1,n_total], b[1]],
         .
         .
         .
         [A[m,0], A[m,1], ..., A[m,n_total], b[m]],
         [c[0],   c[1], ...,   c[n_total],   0],
         [c'[0],  c'[1], ...,  c'[n_total],  0]]

         for a Phase 1 problem (a Problem in which a basic feasible solution is sought
         prior to maximizing the actual objective. n_total is the total of all variables:
    basis : sequence of int
        The indices of the columns that represent the current basis.
    indx : sequence of int
        Indices of the columns that represent the independent variables x.
    s : int
        Indices which phase of the simplex method is being used.
        s = 1 for Phase 1 or s = 2 for Phase 2.
    maxiter : int
        The maximum number of iterations allowed before the algorithm is
        aborted.

    Return
    ------
    iter : int
        The number of iterations performed.
    status : int
        A flag indicating the status of the solution
        0 : Optimization terminated successfully
        1 : Iteration limit reached
        3 : Problem appears to be unbounded
        4 : Singular matrix
    """
    status = None
    if s == 1:
        s0 = 2
    elif s == 2:
        s0 = 1
    n1 = H.shape[0]
    sol = False
    iter = 0
    while iter < maxiter:
        q = H[-1, :-1] # last row, all columns but last
        jp = argmin(q)
        fm = q[jp]
        if fm >= 0:
            is_bounded = True    # bounded solution
            sol = True
            status = 0
        else:
            q = H[:-s0,jp]
            ip = argmax(q)
            hm = q[ip]
            if hm <= 0:
                is_bounded = False # unbounded solution
                sol = True
                status = 3
            else:
                h1 = zeros(n1-s0)
                for i in xrange(n1-s0):
                    if H[i,jp] > 0:
                        h1[i] = H[i,-1]/H[i,jp]
                    else:
                        h1[i] = Inf
                ip = argmin(h1)
                #minh1 = h1[ip]
                basis[ip] = indx[jp]
                if not _pivot(H,ip,jp):
                    sol = True
                    status = 4
        if sol:
            # Solution acquired
            break
        iter += 1
    else:
        # Maximum iterations reached
        status = 1
    return iter, status

def _pivot(H,ip,jp):
    """ Perform a Gauss-Jordan pivot in the matrix/tableau H, where ip
        is the pivot row and jp is the pivot column.

        Parameters
        ----------
        H : array-like
            A 2D array representing the matrix or tableau on which the
            pivot operation is to be performed.  If the pivot is successful
            H is modified to reflect the result of the pivot operation.
        ip : int
            The row of the pivot element.
        jp : int
            The column of the pivot element.

        Return
        ------
        False if the pivot element value is zero, otherwise True.
    """
    n, m = H.shape
    piv = H[ip,jp]
    if piv == 0:
        return False
    else:
        H[ip,:] /= piv
        for i in xrange(n):
            if i != ip:
                H[i,:] -= H[i,jp]*H[ip,:]
    return True




def _linprog_simplex(c,A_ub=None,b_ub=None,A_eq=None,b_eq=None,
            bounds=None,maxiter=1000,disp=False,callback=None,
            tol=1.0E-12,**unknown_options):
    """
    Solve the following linear programming problem via a two-phase simplex algorithm.

    maximize:     c^T * x

    subject to:   A_ub * x <= b_ub
                  A_eq * x == b_eq

    Parameters
    ----------
    c : array_like
        Coefficients of the linear objective function to be maximized.
    A_ub :
        2-D array which, when matrix-multiplied by x, gives the values of the upper-bound inequality constraints at x.
    b_ub : array_like
        1-D array of values representing the upper-bound of each inequality constraint (row) in A_ub.
    A_eq : array_like
        2-D array which, when matrix-multiplied by x, gives the values of the equality constraints at x.
    b_eq : array_like
        1-D array of values representing the RHS of each equality constraint (row) in A_eq.
    bounds : array_like
        The bounds for each independent variable in the solution, which can take one of three forms::
        None : The default bounds, all variables are restricted to be non-negative.
        (lb,ub) : If a 2-element sequence is provided, the same lower bound (lb) and upper bound (ub) will be
                  applied to all variables.
        [(lb_0,ub_0),(lb_1,ub_1),...] : If an n x 2 sequence is provided, each variable x_i will be bounded by lb_i
                  and ub_i.
        Infinite bounds are specified using -np.inf (negative) or np.inf (positive).
    maxiter : int
       The maximum number of iterations to perform.
    disp : bool
        If True, print exit status message to sys.stdout
    callback : callable
        If a callback function is provide, it will be called within each iteration of the simplex algorithm.
        The callback must have the signature `callback(xk,**kwargs)` where xk is the current solution vector
        and kwargs is a dictionary containing the following::
        "tableau" : The current Simplex algorithm tableau
        "nit" : The current iteration.
        "pivot" : The pivot (row,column) used for the next iteration.
        "phase" : Whether the algorithm is in Phase 1 or Phase 2.
        "bv" : A structured array containing a string representation of each basic variable and its current value.
    tol : float
        The tolerance which determines when a solution is "close enough" to zero in Phase 1 to be considered
        a basic feasible solution or close enough to positive to to serve as an optimal solution.

    Returns
    -------
    x : ndarray
        The independent variable vector which optimizes the linear programming problem.
    success : bool
        Returns True if the algorithm succeeded in finding an optimal solution.
    status : int
        An integer representing the exit status of the optimization::
        -1 : Invalid arguments
         0 : Optimization terminated successfully
         1 : Iteration limit reached
         2 : Problem appears to be infeasible
         3 : Problem appears to be unbounded
    nit : int
        The number of iterations performed.
    message : str
        A string descriptor of the exit status of the optimization.
    bv : tuple
        The basic variables.
    nbv : tuple
        The nonbasic variables.

    Examples
    --------
    Consider the following problem:

    Minimize: f = -1*x[0] + 4*x[1]

    Subject to: -3*x[0] + 1*x[1] <= 6
                 1*x[0] + 2*x[1] <= 4
                            x[1] >= -3

    where:  -inf <= x[0] <= inf

    This problem deviates from the standard linear programming problem.  In standard form, linear programming problems
    assume the variables x are non-negative.  Since the variables don't have standard bounds where 0 <= x <= inf, the
    bounds of the variables must be explicitly set.

    There are two upper-bound constraints, which can be expressed as

    dot(A_ub,x) <= b_ub

    The input for this problem is as follows:
    >>> c = [-1,4]
    >>> A_ub = [[-3,1],
    >>>         [1,2]]
    >>> b_ub = [6,4]
    >>> x0_bounds = (-np.inf,np.inf)
    >>> x1_bounds = (-3,np.inf)
    >>> res = linprog(c,A_ub=A_ub,b_ub=b_ub,bounds=(x0_bounds,x1_bounds),
    ... options={"disp":True})
    >>> print(res)
    Optimization terminated successfully.
         Current function value: 11.428571
         Iterations: 2
    status: 0
    success: True
    fun: 11.428571428571429
    x: array([-1.14285714,  2.57142857])
    message: 'Optimization terminated successfully.'
    nit: 2

    References
    ----------
    .. [1] Dantzig, George B., Linear programming and extensions. Rand
           Corporation Research Study Princeton Univ. Press, Princeton, NJ, 1963
    .. [2] Hillier, S.H. and Lieberman, G.J. (1995), "Introduction to
           Mathematical Programming", McGraw-Hill, Chapter 4.

    """
    status = 0
    messages = { 0 : "Optimization terminated successfully.",
                 1 : "Iteration limit reached.",
                 2 : "Optiization failed. Unable to find a feasible"
                     " starting point.",
                 3 : "Optimization failed. The problem appears to be unbounded.",
                 4 : "Optimization failed. Singular matrix encountered."}
    have_floor_variable = False

    cc = np.asarray(c)

    # The initial value of the objective function element in the tableau
    f0 = 0

    # The number of variables as given by c
    n = len(c)

    # Convert the input arguments to arrays (sized to zero if not provided)
    Aeq = np.asarray(A_eq) if not A_eq is None else np.empty([0,len(cc)])
    Aub = np.asarray(A_ub) if not A_ub is None else np.empty([0,len(cc)])
    beq = np.ravel(np.asarray(b_eq)) if not b_eq is None else np.empty([0])
    bub = np.ravel(np.asarray(b_ub)) if not b_ub is None else np.empty([0])

    # Analyze the bounds and determine what modifications to me made to
    # the constraints in order to accommodate them.
    L = np.zeros(n,dtype=np.float64)
    U = np.ones(n,dtype=np.float64)*np.inf
    if bounds is None or len(bounds) == 0:
        pass
    elif len(bounds) == 1:
        # All bounds are the same
        L = np.asarray(n*bounds[0][0],dtype=np.float64)
        U = np.asarray(n*bounds[0][1],dtype=np.float64)
    else:
        if len(bounds) != n:
            status = -1
            message = "Invalid input.  Length of bounds is inconsistent " \
                      "with the length of c"
        else:
            try:
                for i in range(n):
                    if len(bounds[0]) != 2:
                        raise IndexError()
                    L[i] = bounds[i][0] if not bounds[i][0] is None else -np.inf
                    U[i] = bounds[i][1] if not bounds[i][1] is None else np.inf
            except IndexError as err:
                status = -1
                message = "Invalid input.  bounds must be a n x 2 " \
                          "sequence/array where n = len(c)."

    if np.any(L == -np.inf):
        # If any lower-bound constraint is a free variable
        # add the first column variable as the "floor" variable which
        # accommodates the most negative variable in the problem.
        n = n + 1
        L = np.concatenate([np.array([0]),L])
        U = np.concatenate([np.array([np.inf]),U])
        cc = np.concatenate([np.array([0]),cc])
        Aeq = np.hstack([np.zeros([Aeq.shape[0],1]),Aeq])
        Aub = np.hstack([np.zeros([Aub.shape[0],1]),Aub])
        have_floor_variable = True

    # Now before we deal with any variables with lower bounds < 0,
    # deal with finite bounds which can be simply added as new constraints.
    # Also validate bounds inputs here.
    for i in range(n):
        if(L[i] > U[i]):
            status = -1
            message = "Invalid input.  Lower bound {:d} is greater than " \
                      "upper bound {:d}".format(i,i)

        if np.isinf(L[i]) and L[i] > 0:
            status = -1
            message = "Invalid input.  Lower bound may not be +infinity"

        if np.isinf(U[i]) and U[i] < 0:
            status = -1
            message = "Invalid input.  Upper bound may not be -infinity"

        if np.isfinite(L[i]) and L[i] > 0:
            # Add a new lower-bound (negative upper-bound) constraint
            Aub = np.vstack([Aub, np.zeros(n)])
            Aub[-1,i] = -1
            bub = np.concatenate([bub,np.array([-L[i]])])
            L[i] = 0

        if np.isfinite(U[i]):
            # Add a new upper-bound constraint
            Aub = np.vstack([Aub, np.zeros(n)])
            Aub[-1,i] = 1
            bub = np.concatenate([bub,np.array([U[i]])])
            U[i] = np.inf

    # Now find negative lower bounds (finite or infinite) which require a
    # change of variables or free variables and handle them appropriately
    for i in range(0,n):
        if L[i] < 0:
            if np.isfinite(L[i]) and L[i] < 0:
                # Add a change of variables for x[i]
                # For each row in the constraint matrices, we take the
                # coefficient from column i in A,
                # and subtract the product of that and L[i] to the RHS b
                beq[:] = beq[:] - Aeq[:,i] * L[i]
                bub[:] = bub[:] - Aub[:,i] * L[i]
                # We now have a nonzero initial value for the objective
                # function as well.
                f0 = f0 - cc[i] * L[i]
            else:
                # This is an unrestricted variable, let x[i] = u[i] - v[0]
                # where v is the first column in all matrices.
                Aeq[:,0] = Aeq[:,0] - Aeq[:,i]
                Aub[:,0] = Aub[:,0] - Aub[:,i]
                cc[0] = cc[0] - cc[i]

        if np.isinf(U[i]):
            if U[i] < 0:
                status = -1
                message = "Invalid input.  Upper bound may not be -inf."

    # The number of upper bound constraints (rows in A_ub and elements in b_ub)
    mub = len(bub)

    # The number of equality constraints (rows in A_eq and elements in b_eq)
    meq = len(beq)

    m = mub+meq

    # The number of slack variables (one for each of the upper-bound constraints)
    n_slack = mub

    # The number of artificial variables (one for each constraint)
    n_artificial = m

    try:
        if not Aub is None:
            Aub_rows, Aub_cols = Aub.shape
        else:
            Aub_rows, Aub_cols = 0,0
    except ValueError:
        status = -1
        message = "Invalid input.  A_ub must be two-dimensional"

    try:
        if not Aeq is None:
            Aeq_rows, Aeq_cols = Aeq.shape
        else:
            Aeq_rows, Aeq_cols = 0,0
    except ValueError:
        status = -1
        message = "Invalid input.  A_eq must be two-dimensional"

    if Aeq_rows != meq:
        status = -1
        message = "Invalid input.  The number of rows in A_eq must be equal " \
                  "to the number of values in b_eq"

    if Aub_rows != mub:
        status = -1
        message = "Invalid input.  The number of rows in A_ub must be equal " \
                  "to the number of values in b_ub"

    if Aeq_cols > 0 and Aeq_cols != n:
        status = -1
        message = "Invalid input.  Number of columns in A_eq must be equal " \
                  "to the size of c"

    if Aub_cols > 0 and Aub_cols != n:
        status = -1
        message = "Invalid input.  Number of columns in A_ub must be equal " \
                  "to the size of c"

    if status != 0:
        # Invalid inputs provided
        if disp:
            print(message)
        return Result(x=np.zeros_like(cc),fun=0.0,nit=0,status=int(status),
                      message=message, success=False)

    # Create the tableau
    T = np.zeros([m+2,n+n_slack+n_artificial+1])

    # Insert objective into tableau
    T[-2,:n] = cc
    T[-2,-1] = f0

    b = T[:-1,-1]

    if meq > 0:
        # Add Aeq to the tableau
        T[:meq,:n] = Aeq
        # Add beq to the tableau
        b[:meq] = beq
    if mub > 0:
        # Add Aub to the tableau
        T[meq:meq+mub,:n] = Aub
        # At bub to the tableau
        b[meq:meq+mub] = bub
        # Add the slack variables to the tableau
        np.fill_diagonal(T[meq:m,n:n+n_slack], 1)

    # No negative resource constraints are allowed.
    # Note that this reverses the sign of the slack/surplus variables since
    # multiplication of an inequality by a negative flips the sign.
    for i in range(m):
        if b[i] < 0:
            b[i] *= -1
            T[i,:-1] *= -1

    T[:n_artificial, n+n_slack:n+n_slack+n_artificial] \
        = np.eye(n_artificial)

    # Add an objective term to each of the artificial variable columns
    T[-1,n+n_slack:-1] = 1

    # Make the artificial variables basic feasible variables by subtracting
    # each row with an artificial variable from the Phase 1 objective
    for r in range(n_artificial):
        T[-1,:] = T[-1,:] - T[r,:]

    x, nit1, status, message = lpsimplex(T,n,n_slack,n_artificial,
                                         phase=1,callback=callback,
                                         maxiter=maxiter,tol=tol)

    #basis = np.arange(n,n+m)
    #xindex = np.arange(n)
    #
    #nit1, status = _simplex(H,basis,xindex,1,maxiter)
    #
    #if status != 0:
    #    return Result(x=np.zeros(n),fun=np.nan,nit=nit1,status=int(status),
    #                  message=messages[status], success=False)

    #optx = zeros(n+m)
    #for i in xrange(m):
    #    optx[basis[i]] = T[i,-1]
    #x = optx[:n]

    # if pseudo objective is zero, remove the last row from the tableau and
    # proceed to phase 2
    if abs(T[-1,-1]) < tol:
        # Remove the pseudo-objective row from the tableau
        T = T[:-1,:]
        # Remove the artificial variable columns from the tableau
        T = np.delete(T,np.s_[n+n_slack:n+n_slack+n_artificial],1)
    else:
        status = 2
        message = "Optimization Failed.  Unable to find a feasible starting point."

    if status != 0:
        # Failure to find a feasible starting point
        if disp:
            print(message)
        return Result(x=x,fun=-T[-1,-1],nit=nit1,status=int(status),
                      message=message, success=False)

    # Tableau Finished
    if status == 0:
        x, nit2, status, message = lpsimplex(T,n,n_slack,
                                             n_artificial,maxiter=maxiter,
                                             phase=2,callback=callback,
                                             tol=tol,nit0=nit1)

    # For those variables with finite negative lower bounds,
    # reverse the change of variables
    masked_L = ma.array(L,mask=np.isinf(L),fill_value=0.0).filled()
    x = x + masked_L

    # For those variables with infinite negative lower bounds,
    # take x[i] as the difference between x[i] and the floor variable.
    if have_floor_variable:
        for i in range(1,n):
            if np.isinf(L[i]):
                x[i] -= x[0]
        x = x[1:]

    # Optimization complete at this point
    obj = -T[-1,-1]

    if status in (0,1):
        if disp:
            print(message)
            print("         Current function value: {: <12.6f}".format(obj))
            print("         Iterations: {:d}".format(nit2))
    else:
        if disp:
            print(message)
            print("         Iterations: {:d}".format(nit2))

    return Result(x=x,fun=obj,nit=int(nit2),status=int(status),
                  message=message,success=(status == 0))







def linprog(c,A_eq=None,b_eq=None,A_ub=None,b_ub=None,
            bounds=None,method='simplex',callback=None,
            options=None):
    """
    Minimize a linear objective function subject to linear
    equality and inequality constraints.

    Linear Programming is intended to solve the following problem form:

    Minimize:     c^T * x

    Subject to:   A_ub * x <= b_ub
                  A_eq * x == b_eq

    .. versionadded:: 0.14.0

    Parameters
    ----------
    c : array_like
        Coefficients of the linear objective function to be minimized.
    A_ub :
        2-D array which, when matrix-multiplied by x, gives the values of the
        upper-bound inequality constraints at x.
    b_ub : array_like
        1-D array of values representing the upper-bound of each inequality
        constraint (row) in A_ub.
    A_eq : array_like
        2-D array which, when matrix-multiplied by x, gives the values of the
        equality constraints at x.
    b_eq : array_like
        1-D array of values representing the RHS of each equality constraint
        (row) in A_eq.
    objtype : str
        The type of objective function represented by c.  Must be either 'max'
        (default) or 'min'
    bounds : sequence, optional
        ``(min, max)`` pairs for each element in ``x``, defining
        the bounds on that parameter. Use None for one of ``min`` or
        ``max`` when there is no bound in that direction. By default
        bounds are ``(0,None)`` (non-negative)
        If a sequence containing a single tuple is provided, then ``min`` and
        ``max`` will be applied to all variables in the problem.
    method : str, optional
        Type of solver.  At this time only 'simplex' is supported.
    callback : callable
        If a callback function is provide, it will be called within each
        iteration of the simplex algorithm. The callback must have the signature
        `callback(xk,**kwargs)` where xk is the current solution vector
        and kwargs is a dictionary containing the following::
        "tableau" : The current Simplex algorithm tableau
        "nit" : The current iteration.
        "pivot" : The pivot (row,column) used for the next iteration.
        "phase" : Whether the algorithm is in Phase 1 or Phase 2.
        "bv" : A structured array containing a string representation of each
               basic variable and its current value.
    options : dict, optional
        A dictionary of solver options. All methods accept the following
        generic options:
            maxiter : int
                Maximum number of iterations to perform.
            disp : bool
                Set to True to print convergence messages.
        For method-specific options, see :func:`show_options()`.

    Returns
    -------
    x : ndarray
        The independent variable vector which optimizes the
        linear programming problem.
    success : bool
        Returns True if the algorithm succeeded in finding an optimal solution.
    status : int
        An integer representing the exit status of the optimization::
        -1 : Invalid arguments
         0 : Optimization terminated successfully
         1 : Iteration limit reached
         2 : Problem appears to be infeasible
         3 : Problem appears to be unbounded
    nit : int
        The number of iterations performed.
    message : str
        A string descriptor of the exit status of the optimization.
    bv : tuple
        The basic variables.
    nbv : tuple
        The nonbasic variables.

    Examples
    --------
    Consider the following problem:

    Minimize: f = -1*x[0] + 4*x[1]

    Subject to: -3*x[0] + 1*x[1] <= 6
                 1*x[0] + 2*x[1] <= 4
                            x[1] >= -3

    where:  -inf <= x[0] <= inf

    This problem deviates from the standard linear programming problem.
    In standard form, linear programming problems assume the variables x are
    non-negative.  Since the variables don't have standard bounds where
    0 <= x <= inf, the bounds of the variables must be explicitly set.

    There are two upper-bound constraints, which can be expressed as

    dot(A_ub,x) <= b_ub

    The input for this problem is as follows:
    >>> c = [1,-4] # Note the reversed coefficients for maximization
    >>> A_ub = [[-3,1],
    >>>         [1,2]]
    >>> b_ub = [6,4]
    >>> x0_bounds = (-np.inf,np.inf)
    >>> x1_bounds = (-3,np.inf)
    >>> res = linprog(c,A_ub=A_ub,b_ub=b_ub,bounds=(x0_bounds,x1_bounds),
    ...               objtype='max',disp=True)
    >>> print(res)
    Optimization terminated successfully.
         Current function value: -11.428571
         Iterations: 2
    status: 0
    success: True
    fun: -11.428571428571429
    x: array([-1.14285714,  2.57142857])
    message: 'Optimization terminated successfully.'
    nit: 2

    Note the actual objective value is 11.428571.  In this case we minimized
    the negative of the objective function.

    References
    ----------
    .. [1] Dantzig, George B., Linear programming and extensions. Rand
           Corporation Research Study Princeton Univ. Press, Princeton, NJ, 1963

    .. [2] Hillier, S.H. and Lieberman, G.J. (1995), "Introduction to
           Mathematical Programming", McGraw-Hill, Chapter 4.

    Returns
    -------
    res : Result
        The optimization result represented as a ``Result`` object.
        Important attributes are: ``x`` the solution array, ``success`` a
        Boolean flag indicating if the optimizer exited successfully and
        ``message`` which describes the cause of the termination. See
        `Result` for a description of other attributes.

    See also
    --------
    show_options : Additional options accepted by the solvers

    Notes
    -----
    This section describes the available solvers that can be selected by the
    'method' parameter. The default method is *Simplex*.

    Method *Simplex* uses the Simplex algorithm (as it relates to Linear
    Programming, NOT the Nelder-Mead Simplex) [1]_, [2]_. This algorithm
    should be reasonably reliable and fast.


    """
    meth = method.lower()
    if options is None:
        options = {}

    if meth == 'simplex':
        return _linprog_simplex(c,A_ub=A_ub,b_ub=b_ub,A_eq=A_eq,b_eq=b_eq,
                                bounds=bounds,callback=callback,**options)
    else:
        raise ValueError('Unknown solver %s' % method)

