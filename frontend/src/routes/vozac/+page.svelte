<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';

	onMount(() => {
		// Ako se otvori /vozac bez tokena, automatski preusmjeri na zadanu rutu /vozac/demo
		goto(resolve('/vozac/[token]', { token: 'demo' }), { replaceState: true });
	});
</script>

<div style="padding: 40px; text-align: center; font-family: sans-serif;">
	<p>Preusmjeravanje na rutu vozača…</p>
</div>
