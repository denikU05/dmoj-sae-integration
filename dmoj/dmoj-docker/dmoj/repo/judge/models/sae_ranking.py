import logging
import time
from django.db import transaction
from judge.utils.telemetry import log_step

logger = logging.getLogger('judge.models.submission')

def calculate_and_save_score(analysis, config, bounds, commit: bool = True):
    """
    Calculates sae_score and final_score for a single submission.
    If commit=False, updates are kept in memory (optimized for mass recalculation).
    """
    total_weighted_norm = 0.0
    total_weight = 0.0
    
    for metric_key, metric_val in analysis.metrics.items():
        metric_cfg = config.get(metric_key, {})
        if not metric_cfg.get('enabled', False):
            continue
            
        weight = metric_cfg.get('weight', 1.0)
        direction = metric_cfg.get('direction', 'lower_better')
        
        mbound = bounds.get(metric_key)
        if not mbound:
            continue
            
        min_val = mbound["min"]
        max_val = mbound["max"]
        
        if max_val == min_val:
            norm_val = 1.0
        else:
            if direction == 'lower_better':
                norm_val = (max_val - metric_val) / (max_val - min_val)
            else:  # higher_better
                norm_val = (metric_val - min_val) / (max_val - min_val)
                
        total_weighted_norm += norm_val * weight
        total_weight += weight
        
    sae_score = (total_weighted_norm / total_weight) if total_weight > 0 else 1.0
        
    base_points = analysis.submission.points or 0.0
    problem = analysis.submission.problem
    max_penalty_coeff = getattr(problem, 'sae_max_penalty', 50) / 100.0
    
    effective_multiplier = 1.0 - (max_penalty_coeff * (1.0 - sae_score))
    final_score = base_points * effective_multiplier
    
    analysis.sae_score = sae_score
    analysis.final_score = final_score
    
    if commit:
        analysis.save(update_fields=['sae_score', 'final_score'])


def process_sae_recalculation(analysis_instance):
    """
    O(1) recalculation engine. Operates globally per problem.
    Triggers bulk_update mass recalculation if bounds are changed to ensure performance.
    """
    try:
        t_start = time.time()

        submission = analysis_instance.submission
        problem = submission.problem
        
        config = problem.sae_metrics_config or {}
        bounds = problem.sae_bounds or {}
        new_metrics = analysis_instance.metrics
        bounds_changed = False
        
        for metric_key, metric_val in new_metrics.items():
            metric_cfg = config.get(metric_key, {})
            if not metric_cfg.get('enabled', False):
                continue
                
            if metric_key not in bounds:
                bounds[metric_key] = {"min": metric_val, "max": metric_val}
                bounds_changed = True
            else:
                if metric_val < bounds[metric_key]["min"]:
                    bounds[metric_key]["min"] = metric_val
                    bounds_changed = True
                if metric_val > bounds[metric_key]["max"]:
                    bounds[metric_key]["max"] = metric_val
                    bounds_changed = True

        if bounds_changed:
            logger.info(f"SAE bounds changed for problem {problem.code}. Triggering mass recalculation.")
            
            with transaction.atomic():
                problem.sae_bounds = bounds
                problem.save(update_fields=['sae_bounds'])
                
                from judge.models.submission import SubmissionAnalysis
                # Use iterator() to save RAM when processing tens of thousands of submissions
                queryset = SubmissionAnalysis.objects.filter(
                    submission__problem=problem
                ).select_related('submission', 'submission__problem').iterator()
                
                analyses_to_update = []
                
                for old_analysis in queryset:
                    # Pass commit=False to avoid saving each object individually
                    calculate_and_save_score(old_analysis, config, bounds, commit=False)
                    analyses_to_update.append(old_analysis)
                    
                    # Save in batches of 1000 to prevent memory overflow
                    if len(analyses_to_update) >= 1000:
                        SubmissionAnalysis.objects.bulk_update(
                            analyses_to_update, 
                            ['sae_score', 'final_score']
                        )
                        analyses_to_update.clear()
                
                # Save the remaining tail of the batch
                if analyses_to_update:
                    SubmissionAnalysis.objects.bulk_update(
                        analyses_to_update, 
                        ['sae_score', 'final_score']
                    )
        else:
            logger.debug(f"SAE bounds intact for problem {problem.code}. Fast O(1) scoring applied.")
            calculate_and_save_score(analysis_instance, config, bounds)

    except Exception as e:
        print(f"[ERROR-SAE] Critical failure in recalculation: {e}")
        print(traceback.format_exc())
        raise

    finally:
        duration = time.time() - t_start
        sub_id = getattr(analysis_instance, 'submission_id', analysis_instance.pk)
        log_step(sub_id, 'DB_UPDATE', duration)
        print(f"[DEBUG] DB_UPDATE log attempt for {sub_id} finished.")