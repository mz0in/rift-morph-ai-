<script lang="ts">
  import { state } from "../../stores";
  import RiftSvg from "../../icons/RiftSvg.svelte";
  import type { AgentRegistryItem } from "../../../../src/types";

  export let focused: boolean = false;
  export let handleRunAgent: (agent_type: string) => void;
  export let agent: AgentRegistryItem;
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- only disabling this because we already are handling onkeydown-->
<div class="bg-[var(--vscode-editor-background)]">
  <div
    class={`flex flex-col hover:cursor-pointer pl-2 py-2
    ${
      focused
        ? "bg-[var(--vscode-editor-hoverHighlightBackground)]"
        : "bg-[var(--vscode-editor-background)] hover:bg-[var(--vscode-list-hoverBackground)]"
    }`}
    on:click={() => handleRunAgent(agent.agent_type)}
  >
    <div class="flex flex-row ml-[6px]">
      <div
        class="flex items-center justify-center w-[16px] h-[16px] mr-2 scale-125"
      >
        {#if agent.agent_icon}
          {@html agent.agent_icon}
        {:else}
          <RiftSvg />
        {/if}
      </div>

      <!-- {agent.agent_type} -->
      {agent.display_name}
    </div>
    <!-- <div>
    {agent.display_name}
  </div> -->
    <div
      class="text-[var(--vscode-gitDecoration-ignoredResourceForeground)] truncate overflow-hidden ml-[2px]"
    >
      {agent.agent_description}
    </div>
  </div>
</div>
