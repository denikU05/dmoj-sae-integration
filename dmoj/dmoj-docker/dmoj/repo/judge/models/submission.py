import hashlib
import hmac

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from reversion import revisions

from judge.judgeapi import abort_submission, judge_submission
from judge.models.problem import Problem, SubmissionSourceAccess
from judge.models.profile import Profile
from judge.models.runtime import Language
from judge.utils.unicode import utf8bytes

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
import logging
from judge.sae_metrics import METRIC_TRANSLATIONS

__all__ = ['SUBMISSION_RESULT', 'Submission', 'SubmissionSource', 'SubmissionTestCase']

SUBMISSION_RESULT = (
    ('AC', _('Accepted')),
    ('WA', _('Wrong Answer')),
    ('TLE', _('Time Limit Exceeded')),
    ('MLE', _('Memory Limit Exceeded')),
    ('OLE', _('Output Limit Exceeded')),
    ('IR', _('Invalid Return')),
    ('RTE', _('Runtime Error')),
    ('CE', _('Compile Error')),
    ('IE', _('Internal Error')),
    ('SC', _('Short Circuited')),
    ('AB', _('Aborted')),
)


@revisions.register(follow=['test_cases'])
class Submission(models.Model):
    STATUS = (
        ('QU', _('Queued')),
        ('P', _('Processing')),
        ('G', _('Grading')),
        ('D', _('Completed')),
        ('IE', _('Internal Error')),
        ('CE', _('Compile Error')),
        ('AB', _('Aborted')),
    )
    IN_PROGRESS_GRADING_STATUS = ('QU', 'P', 'G')
    RESULT = SUBMISSION_RESULT
    USER_DISPLAY_CODES = {
        'AC': _('Accepted'),
        'WA': _('Wrong Answer'),
        'SC': _('Short Circuited'),
        'TLE': _('Time Limit Exceeded'),
        'MLE': _('Memory Limit Exceeded'),
        'OLE': _('Output Limit Exceeded'),
        'IR': _('Invalid Return'),
        'RTE': _('Runtime Error'),
        'CE': _('Compile Error'),
        'IE': _('Internal Error (judging server error)'),
        'QU': _('Queued'),
        'P': _('Processing'),
        'G': _('Grading'),
        'D': _('Completed'),
        'AB': _('Aborted'),
    }

    user = models.ForeignKey(Profile, verbose_name=_('user'), on_delete=models.CASCADE, db_index=False)
    problem = models.ForeignKey(Problem, verbose_name=_('problem'), on_delete=models.CASCADE, db_index=False)
    date = models.DateTimeField(verbose_name=_('submission time'), auto_now_add=True, db_index=True)
    time = models.FloatField(verbose_name=_('execution time'), null=True)
    memory = models.FloatField(verbose_name=_('memory usage'), null=True)
    points = models.FloatField(verbose_name=_('points granted'), null=True)
    language = models.ForeignKey(Language, verbose_name=_('submission language'),
                                 on_delete=models.CASCADE, db_index=False)
    status = models.CharField(verbose_name=_('status'), max_length=2, choices=STATUS, default='QU', db_index=True)
    result = models.CharField(verbose_name=_('result'), max_length=3, choices=SUBMISSION_RESULT,
                              default=None, null=True, blank=True)
    error = models.TextField(verbose_name=_('compile errors'), null=True, blank=True)
    current_testcase = models.IntegerField(default=0)
    batch = models.BooleanField(verbose_name=_('batched cases'), default=False)
    case_points = models.FloatField(verbose_name=_('test case points'), default=0)
    case_total = models.FloatField(verbose_name=_('test case total points'), default=0)
    judged_on = models.ForeignKey('Judge', verbose_name=_('judged on'), null=True, blank=True,
                                  on_delete=models.SET_NULL)
    judged_date = models.DateTimeField(verbose_name=_('submission judge time'), default=None, null=True)
    rejudged_date = models.DateTimeField(verbose_name=_('last rejudge date by admin'), null=True, blank=True)
    is_pretested = models.BooleanField(verbose_name=_('was ran on pretests only'), default=False)
    contest_object = models.ForeignKey('Contest', verbose_name=_('contest'), null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name='+', db_index=False)
    locked_after = models.DateTimeField(verbose_name=_('submission lock'), null=True, blank=True)

    @classmethod
    def result_class_from_code(cls, result, case_points, case_total):
        if result == 'AC':
            if case_points == case_total:
                return 'AC'
            return '_AC'
        return result

    @property
    def result_class(self):
        # This exists to save all these conditionals from being executed (slowly) in each row.html template
        if self.status in ('IE', 'CE'):
            return self.status
        return Submission.result_class_from_code(self.result, self.case_points, self.case_total)

    @property
    def memory_bytes(self):
        return self.memory * 1024 if self.memory is not None else 0

    @property
    def short_status(self):
        return self.result or self.status

    @property
    def long_status(self):
        return Submission.USER_DISPLAY_CODES.get(self.short_status, '')

    @cached_property
    def is_locked(self):
        return self.locked_after is not None and self.locked_after < timezone.now()

    def judge(self, *args, rejudge=False, force_judge=False, rejudge_user=None, **kwargs):
        if force_judge or not self.is_locked:
            if rejudge:
                with revisions.create_revision(manage_manually=True):
                    if rejudge_user:
                        revisions.set_user(rejudge_user)
                    revisions.set_comment('Rejudged')
                    revisions.add_to_revision(self)
            judge_submission(self, *args, rejudge=rejudge, **kwargs)

    judge.alters_data = True

    def abort(self):
        abort_submission(self)

    abort.alters_data = True

    def can_see_detail(self, user):
        if not user.is_authenticated:
            return False
        profile = user.profile
        source_visibility = self.problem.submission_source_visibility
        if self.problem.is_editable_by(user):
            return True
        elif user.has_perm('judge.view_all_submission'):
            return True
        elif self.user_id == profile.id:
            return True
        elif source_visibility == SubmissionSourceAccess.ALWAYS:
            return True
        elif source_visibility == SubmissionSourceAccess.SOLVED and \
                (self.problem.is_public or self.problem.testers.filter(id=profile.id).exists()) and \
                self.problem.is_solved_by(user):
            return True
        elif source_visibility == SubmissionSourceAccess.ONLY_OWN and \
                self.problem.testers.filter(id=profile.id).exists():
            return True

        contest = self.contest_object
        # If user is an author or curator of the contest the submission was made in, or they can see in-contest subs
        if contest is not None and (
            user.profile.id in contest.editor_ids or
            contest.view_contest_submissions.filter(id=user.profile.id).exists() or
            (contest.tester_see_submissions and user.profile.id in contest.tester_ids)
        ):
            return True

        return False

    def update_contest(self):
        try:
            contest = self.contest
        except AttributeError:
            return

        contest_problem = contest.problem
        contest.points = round(self.case_points / self.case_total * contest_problem.points
                               if self.case_total > 0 else 0, 3)
        if not contest_problem.partial and contest.points != contest_problem.points:
            contest.points = 0
        contest.save()
        contest.participation.recompute_results()

    update_contest.alters_data = True

    @property
    def is_graded(self):
        return self.status not in ('QU', 'P', 'G')

    @cached_property
    def contest_key(self):
        if hasattr(self, 'contest'):
            return self.contest_object.key

    def __str__(self):
        return _('Submission %(id)d of %(problem)s by %(user)s') % {
            'id': self.id, 'problem': self.problem, 'user': self.user.user.username,
        }

    def get_absolute_url(self):
        return reverse('submission_status', args=(self.id,))

    @cached_property
    def contest_or_none(self):
        try:
            return self.contest
        except ObjectDoesNotExist:
            return None

    @classmethod
    def get_id_secret(cls, sub_id):
        return (hmac.new(utf8bytes(settings.EVENT_DAEMON_SUBMISSION_KEY), b'%d' % sub_id, hashlib.sha512)
                    .hexdigest()[:16] + '%08x' % sub_id)

    @cached_property
    def id_secret(self):
        return self.get_id_secret(self.id)

    class Meta:
        permissions = (
            ('abort_any_submission', _('Abort any submission')),
            ('rejudge_submission', _('Rejudge the submission')),
            ('rejudge_submission_lot', _('Rejudge a lot of submissions')),
            ('spam_submission', _('Submit without limit')),
            ('view_all_submission', _('View all submission')),
            ('resubmit_other', _("Resubmit others' submission")),
            ('lock_submission', _('Change lock status of submission')),
        )
        verbose_name = _('submission')
        verbose_name_plural = _('submissions')

        indexes = [
            # For problem submission rankings
            models.Index(fields=['problem', 'user', '-points', '-time']),

            # For contest problem submission rankings
            models.Index(fields=['contest_object', 'problem', 'user', '-points', '-time']),

            # For main submission list filtering by some combination of result and language
            models.Index(fields=['result', '-id']),
            models.Index(fields=['result', 'language', '-id']),
            models.Index(fields=['language', '-id']),

            # For filtered main submission list result charts
            models.Index(fields=['result', 'problem']),
            models.Index(fields=['language', 'problem', 'result']),

            # For problem submissions result chart
            models.Index(fields=['problem', 'result']),

            # For user_attempted_ids and own problem submissions result chart
            models.Index(fields=['user', 'problem', 'result']),

            # For user_completed_ids
            models.Index(fields=['user', 'result']),
        ]


class SubmissionSource(models.Model):
    submission = models.OneToOneField(Submission, on_delete=models.CASCADE, verbose_name=_('associated submission'),
                                      related_name='source')
    source = models.TextField(verbose_name=_('source code'), max_length=65536)

    def __str__(self):
        return _('Source of %(submission)s') % {'submission': self.submission}

    class Meta:
        verbose_name = _('submission source')
        verbose_name_plural = _('submission sources')


@revisions.register()
class SubmissionTestCase(models.Model):
    RESULT = SUBMISSION_RESULT

    submission = models.ForeignKey(Submission, verbose_name=_('associated submission'), db_index=False,
                                   related_name='test_cases', on_delete=models.CASCADE)
    case = models.IntegerField(verbose_name=_('test case ID'))
    status = models.CharField(max_length=3, verbose_name=_('status flag'), choices=SUBMISSION_RESULT)
    time = models.FloatField(verbose_name=_('execution time'), null=True)
    memory = models.FloatField(verbose_name=_('memory usage'), null=True)
    points = models.FloatField(verbose_name=_('points granted'), null=True)
    total = models.FloatField(verbose_name=_('points possible'), null=True)
    batch = models.IntegerField(verbose_name=_('batch number'), null=True)
    feedback = models.CharField(max_length=50, verbose_name=_('judging feedback'), blank=True)
    extended_feedback = models.TextField(verbose_name=_('extended judging feedback'), blank=True)
    output = models.TextField(verbose_name=_('program output'), blank=True)

    @property
    def long_status(self):
        return Submission.USER_DISPLAY_CODES.get(self.status, '')

    @property
    def result_class(self):
        if self.status in ('IE', 'CE'):
            return self.status
        return Submission.result_class_from_code(self.status, self.points, self.total)

    class Meta:
        unique_together = ('submission', 'case')
        verbose_name = _('submission test case')
        verbose_name_plural = _('submission test cases')


# SAE Integration

class SubmissionAnalysis(models.Model):
    submission = models.OneToOneField(
        'judge.Submission',
        on_delete=models.CASCADE,
        related_name='analysis',
        primary_key=True
    )
    
    metrics = models.JSONField(
        default=dict,
        verbose_name=_('metrics data'),
        help_text=_('Flexible JSON field storing all extracted tree-sitter metrics.')
    )
    analysis_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('analysis timestamp')
    )
    sae_score = models.FloatField(
        default=0.0,
        verbose_name=_('SAE multiplier')
    )
    final_score = models.FloatField(
        default=0.0,
        verbose_name=_('final score')
    )

    class Meta:
        db_table = 'judge_submissionanalysis'
        verbose_name = _('submission analysis')
        verbose_name_plural = _('submission analyses')

    def get_localized_metrics(self, lang_code: str = 'en') -> list[dict]:
        """
        Dynamically transforms raw metrics JSON into a translated format for the frontend.
        Filters the output to include ONLY metrics explicitly enabled in the Problem's configuration.
        """
        if lang_code not in {'ru', 'en'}:
            lang_code = 'en'
        
        localized_list = []

        # Optimize by using dict.get() with a default empty dict for safe fallback
        problem_config = getattr(self.submission.problem, 'sae_metrics_config', {}) or {}
        
        for key, value in self.metrics.items():
            metric_config = problem_config.get(key, {})
            
            # Skip if the metric is disabled or missing from the configuration
            if not metric_config.get('enabled', False):
                continue
                
            translations = METRIC_TRANSLATIONS.get(key, {})
            display_name = translations.get(lang_code, key.replace('_', ' ').title())
            
            localized_list.append({
                'key': key,
                'name': display_name,
                'value': value
            })

        return localized_list


logger = logging.getLogger('judge.models.submission')


@receiver(post_save, sender='judge.Submission')
def trigger_sae_on_ac(sender, instance, created, **kwargs):
    """
    Triggers static analysis via Celery when a submission is successfully judged (AC).
    Uses transaction.on_commit to prevent database race conditions.
    """
    if instance.status == 'D' and getattr(instance, 'result', None) == 'AC':
        logger.debug(f"Submission {instance.id} state is AC. Initiating background metrics recalculation.")
        
        def dispatch_task():
            try:
                from judge.tasks.submission import run_static_analysis
                # Celery Anti-pattern avoided: Passing only the ID. 
                # The worker must query the DB for source_code to prevent overloading Redis/RabbitMQ.
                run_static_analysis.delay(submission_id=instance.id)
                logger.info(f"SAE task queued for submission {instance.id}")
            except Exception as e:
                logger.error(f"Failed to queue SAE task for submission {instance.id}: {str(e)}")

        transaction.on_commit(dispatch_task)


@receiver(post_save, sender='judge.SubmissionAnalysis')
def trigger_recalculation_on_analysis_save(sender, instance, created, **kwargs):
    """
    Catches the Celery metrics save event and triggers ranking score recalculation.
    Protected against infinite recursion via update_fields subset inspection.
    """
    update_fields = kwargs.get('update_fields')
    
    # Robust recursion protection: abort if score updates are present in the fields.
    # Strict set equality (==) is brittle and fails if a concurrent save adds another field.
    if update_fields and ('sae_score' in update_fields or 'final_score' in update_fields):
        return

    def process_recalculation():
        try:
            from judge.sae_ranking import process_sae_recalculation
            process_sae_recalculation(instance)
        except Exception as e:
            logger.error(f"Error during SAE score recalculation for submission {instance.submission_id}: {str(e)}")

    # Ensure ranking logic executes only after the metrics are fully flushed to the database.
    transaction.on_commit(process_recalculation)

@receiver(post_delete, sender=SubmissionAnalysis)
def reset_sae_bounds_on_delete(sender, instance, **kwargs):
    """
    Deletes min and max
    """
    problem = instance.submission.problem
    if problem.sae_bounds:
        problem.sae_bounds = {}
        problem.save(update_fields=['sae_bounds'])
        logger.info(f"SAE bounds cleared for {problem.code} due to deletion.")