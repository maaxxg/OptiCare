<script lang="ts">
	import { getPatients, type Patient } from '#lib/stores/patients.js';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	// Nothing is planned yet: there is no planner/assignment API. Requests are
	// shown as received, with no invented times, until assignments exist.
	const patients: Patient[] = getPatients();

	const groups = [
		{
			color: 'peach',
			title: 'Treba prijevoz – čeka planiranje',
			rows: patients.filter((p) => p.needsTransport)
		},
		{
			color: 'green',
			title: 'Dolazi samostalno',
			rows: patients.filter((p) => !p.needsTransport)
		}
	];
</script>

<svelte:head>
	<title>OptiCare — Raspored pacijenata</title>
</svelte:head>

<div class="page-wide">
	<div class="schedule-top-nav">
		<div class="logo-dot"></div>
		<button class="back-link" onclick={() => goto(resolve('/'))}>← Povratak</button>
	</div>

	<div class="schedule-header-row">
		<h1 class="schedule-main-title">Raspored pacijenata</h1>
	</div>

	<div class="schedule-legend">
		{#each groups as group (group.color)}
			<div class="legend-item">
				<div class="legend-square {group.color}"></div>
				<span>{group.title}</span>
			</div>
		{/each}
	</div>

	{#if patients.length === 0}
		<p class="empty-state">Još nema unesenih zahtjeva.</p>
	{:else}
		<p class="page-subtitle">
			Termini i prijevoz još nisu planirani. Vremena će biti prikazana nakon što medicinska sestra
			potvrdi plan.
		</p>

		<div class="schedule-table-wrap">
			<div class="schedule-table">
				<div class="table-header-pill">
					<span>Osoba</span>
					<span>Opis problema</span>
					<span>Mjesto stanovanja</span>
					<span class="center-col">Vrijeme polaska</span>
					<span class="center-col">Vrijeme pregleda</span>
					<span class="center-col">Vrijeme povratka</span>
				</div>

				{#each groups as group (group.color)}
					{#if group.rows.length > 0}
						<section class="schedule-group">
							<div class="group-title {group.color}">{group.title}</div>
							<div class="group-container {group.color}">
								{#each group.rows as p (p.id)}
									<div class="schedule-row">
										<div class="col-person">
											{p.name}
											{#if p.willingToDrive}
												<br /><span class="badge badge-green">Nudi prijevoz</span>
											{/if}
										</div>
										<div class="col-exam">{p.description}</div>
										<div class="col-clinic">{p.location}</div>
										<span class="center-col"><span class="time-badge-pill">—</span></span>
										<span class="center-col"><span class="time-badge-pill">—</span></span>
										<span class="center-col"><span class="time-badge-pill">—</span></span>
									</div>
								{/each}
							</div>
						</section>
					{/if}
				{/each}
			</div>
		</div>
	{/if}
</div>
