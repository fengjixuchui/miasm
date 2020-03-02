#                                                                              #
#                     Simplification methods library                           #
#                                                                              #

import logging

from future.utils import viewitems

from miasm.expression import simplifications_common
from miasm.expression import simplifications_cond
from miasm.expression import simplifications_explicit
from miasm.expression.expression_helper import fast_unify
import miasm.expression.expression as m2_expr

# Expression Simplifier
# ---------------------

log_exprsimp = logging.getLogger("exprsimp")
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("[%(levelname)-8s]: %(message)s"))
log_exprsimp.addHandler(console_handler)
log_exprsimp.setLevel(logging.WARNING)


class ExpressionSimplifier(object):

    """Wrapper on expression simplification passes.

    Instance handle passes lists.

    Available passes lists are:
     - commons: common passes such as constant folding
     - heavy  : rare passes (for instance, in case of obfuscation)
    """

    # Common passes
    PASS_COMMONS = {
        m2_expr.ExprOp: [
            simplifications_common.simp_cst_propagation,
            simplifications_common.simp_cond_op_int,
            simplifications_common.simp_cond_factor,
            simplifications_common.simp_add_multiple,
            # CC op
            simplifications_common.simp_cc_conds,
            simplifications_common.simp_subwc_cf,
            simplifications_common.simp_subwc_of,
            simplifications_common.simp_sign_subwc_cf,
            simplifications_common.simp_double_zeroext,
            simplifications_common.simp_double_signext,
            simplifications_common.simp_zeroext_eq_cst,
            simplifications_common.simp_ext_eq_ext,

            simplifications_common.simp_cmp_int,
            simplifications_common.simp_cmp_bijective_op,
            simplifications_common.simp_sign_inf_zeroext,
            simplifications_common.simp_cmp_int_int,
            simplifications_common.simp_ext_cst,
            simplifications_common.simp_zeroext_and_cst_eq_cst,
            simplifications_common.simp_test_signext_inf,
            simplifications_common.simp_test_zeroext_inf,
            simplifications_common.simp_cond_inf_eq_unsigned_zero,
            simplifications_common.simp_compose_and_mask,
        ],

        m2_expr.ExprSlice: [
            simplifications_common.simp_slice,
            simplifications_common.simp_slice_of_ext,
            simplifications_common.simp_slice_of_op_ext,
        ],
        m2_expr.ExprCompose: [simplifications_common.simp_compose],
        m2_expr.ExprCond: [
            simplifications_common.simp_cond,
            simplifications_common.simp_cond_zeroext,
            simplifications_common.simp_cond_add,
            # CC op
            simplifications_common.simp_cond_flag,
            simplifications_common.simp_cmp_int_arg,

            simplifications_common.simp_cond_eq_zero,
            simplifications_common.simp_x_and_cst_eq_cst,
            simplifications_common.simp_cond_logic_ext,
            simplifications_common.simp_cond_sign_bit,
            simplifications_common.simp_cond_eq_1_0,
        ],
        m2_expr.ExprMem: [simplifications_common.simp_mem],

    }


    # Heavy passes
    PASS_HEAVY = {}

    # Cond passes
    PASS_COND = {
        m2_expr.ExprSlice: [
            simplifications_cond.expr_simp_inf_signed,
            simplifications_cond.expr_simp_inf_unsigned_inversed
        ],
        m2_expr.ExprOp: [
            simplifications_cond.expr_simp_inverse,
        ],
        m2_expr.ExprCond: [
            simplifications_cond.expr_simp_equal
        ]
    }


    # Available passes lists are:
    #  - highlevel: transform high level operators to explicit computations
    PASS_HIGH_TO_EXPLICIT = {
        m2_expr.ExprOp: [
            simplifications_explicit.simp_flags,
            simplifications_explicit.simp_ext,
        ],
    }


    def __init__(self):
        self.expr_simp_cb = {}
        self.simplified_exprs = set()

    def enable_passes(self, passes):
        """Add passes from @passes
        @passes: dict(Expr class : list(callback))

        Callback signature: Expr callback(ExpressionSimplifier, Expr)
        """

        # Clear cache of simplifiied expressions when adding a new pass
        self.simplified_exprs.clear()

        for k, v in viewitems(passes):
            self.expr_simp_cb[k] = fast_unify(self.expr_simp_cb.get(k, []) + v)

    def apply_simp(self, expression):
        """Apply enabled simplifications on expression
        @expression: Expr instance
        Return an Expr instance"""

        cls = expression.__class__
        debug_level = log_exprsimp.level >= logging.DEBUG
        for simp_func in self.expr_simp_cb.get(cls, []):
            # Apply simplifications
            before = expression
            expression = simp_func(self, expression)
            after = expression

            if debug_level and before != after:
                log_exprsimp.debug("[%s] %s => %s", simp_func, before, after)

            # If class changes, stop to prevent wrong simplifications
            if expression.__class__ is not cls:
                break

        return expression

    def expr_simp(self, expression):
        """Apply enabled simplifications on expression and find a stable state
        @expression: Expr instance
        Return an Expr instance"""

        if expression in self.simplified_exprs:
            return expression

        # Find a stable state
        while True:
            # Canonize and simplify
            e_new = self.apply_simp(expression.canonize())
            if e_new == expression:
                break

            # Launch recursivity
            expression = self.expr_simp_wrapper(e_new)
            self.simplified_exprs.add(expression)
        # Mark expression as simplified
        self.simplified_exprs.add(e_new)

        return e_new

    def expr_simp_wrapper(self, expression, callback=None):
        """Apply enabled simplifications on expression
        @expression: Expr instance
        @manual_callback: If set, call this function instead of normal one
        Return an Expr instance"""

        if expression in self.simplified_exprs:
            return expression

        if callback is None:
            callback = self.expr_simp

        return expression.visit(callback, lambda e: e not in self.simplified_exprs)

    def __call__(self, expression, callback=None):
        "Wrapper on expr_simp_wrapper"
        return self.expr_simp_wrapper(expression, callback)


# Public ExprSimplificationPass instance with commons passes
expr_simp = ExpressionSimplifier()
expr_simp.enable_passes(ExpressionSimplifier.PASS_COMMONS)

expr_simp_high_to_explicit = ExpressionSimplifier()
expr_simp_high_to_explicit.enable_passes(ExpressionSimplifier.PASS_HIGH_TO_EXPLICIT)

expr_simp_explicit = ExpressionSimplifier()
expr_simp_explicit.enable_passes(ExpressionSimplifier.PASS_COMMONS)
expr_simp_explicit.enable_passes(ExpressionSimplifier.PASS_HIGH_TO_EXPLICIT)
