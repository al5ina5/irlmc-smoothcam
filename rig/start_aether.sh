#!/bin/bash
cd "/home/alsinas/Minecraft Servers/LocalAether2-SMP"
exec "$HOME/.local/share/PrismLauncher/java/java-runtime-epsilon/bin/java" -Xms3G -Xmx6G \
  @libraries/net/neoforged/neoforge/26.1.2.106/unix_args.txt nogui
